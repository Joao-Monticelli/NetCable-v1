// NetCable QA robot.
//
// Starts an ISOLATED instance (backend + frontend + fake SMTP, temporary database),
// uses the app like a real user (scripted scenarios + free exploration) and writes a
// report to qa/relatorios/<date-time>/ (relatorio.html and resumo.md).
// No AI involved: runs without spending tokens. Usage: `npm run qa` (or `npm run qa:quick`).
import { chromium } from 'playwright-core'
import { spawn, execSync } from 'node:child_process'
import fs from 'node:fs'
import http from 'node:http'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import crypto from 'node:crypto'

const AQUI = path.dirname(fileURLToPath(import.meta.url))
const RAIZ = path.resolve(AQUI, '..')
const RAPIDO = process.argv.includes('--rapido')
const PORTA_API = Number(process.env.QA_API_PORT || 8011)
const PORTA_WEB = Number(process.env.QA_WEB_PORT || 5184)
const PORTA_SMTP = Number(process.env.QA_SMTP_PORT || 2526)
const ADMIN = { usuario: 'qa-admin', senha: 'qa-senha-forte-123' }
const PASSOS_EXPLORACAO = RAPIDO ? 25 : 70
// QA_MODO=unica testa como a imagem Docker única: o backend serve a interface já compilada (frontend/dist).
const MODO_UNICO = process.env.QA_MODO === 'unica'

// IP da rede local: testar por http://IP reproduz o homelab (contexto "não seguro").
const ipLocal = Object.values(os.networkInterfaces()).flat().find(i => i && i.family === 'IPv4' && !i.internal)?.address
const WEB = `http://${ipLocal || '127.0.0.1'}:${MODO_UNICO ? PORTA_API : PORTA_WEB}`
const API = `http://127.0.0.1:${PORTA_API}/api`

const agora = new Date()
const carimbo = new Date(agora - agora.getTimezoneOffset() * 60000).toISOString().replace(/[:T]/g, '-').slice(0, 16) // hora local
const PASTA = path.join(AQUI, 'relatorios', carimbo)
const PRINTS = path.join(PASTA, 'prints')
fs.mkdirSync(PRINTS, { recursive: true })
const TEMP = fs.mkdtempSync(path.join(os.tmpdir(), 'netcable-qa-'))
const CAIXA_EMAIL = path.join(TEMP, 'emails.jsonl')

const log = (...a) => console.log('[qa]', ...a)
const esperar = (ms) => new Promise(r => setTimeout(r, ms))

// ----------------------------------------------------------------------------- processos
const processos = []
function iniciar(nome, cmd, args, opcoes) {
  // No Windows, npx é um .cmd e precisa de shell: passa a linha inteira (sem argumentos soltos).
  const viaShell = process.platform === 'win32' && !cmd.endsWith('.exe')
  const p = viaShell ? spawn([cmd, ...args].join(' '), { ...opcoes, shell: true, windowsHide: true }) : spawn(cmd, args, { ...opcoes, windowsHide: true })
  const saida = fs.createWriteStream(path.join(TEMP, `${nome}.log`))
  p.stdout?.pipe(saida); p.stderr?.pipe(saida)
  processos.push({ nome, p })
  return p
}
function encerrarTudo() {
  for (const { p } of processos) {
    try {
      if (process.platform === 'win32') execSync(`taskkill /pid ${p.pid} /T /F`, { stdio: 'ignore' })
      else p.kill('SIGTERM')
    } catch { /* já encerrado */ }
  }
}
process.on('exit', encerrarTudo)
process.on('SIGINT', () => { encerrarTudo(); process.exit(130) })

async function aguardarUrl(url, ms = 90000) {
  const fim = Date.now() + ms
  while (Date.now() < fim) {
    try { const r = await fetch(url); if (r.ok) return } catch { /* ainda subindo */ }
    await esperar(700)
  }
  throw new Error(`Timeout esperando ${url}`)
}

function pythonDoBackend() {
  if (process.env.QA_PYTHON) return process.env.QA_PYTHON // ex.: um Python 3.11 com pysnmp (métricas SNMP)
  const candidatos = [path.join(RAIZ, 'backend', 'venv', 'Scripts', 'python.exe'), path.join(RAIZ, 'backend', 'venv', 'bin', 'python')]
  return candidatos.find(fs.existsSync) || (process.platform === 'win32' ? 'python' : 'python3')
}

async function subirAmbiente() {
  // Backend numa cópia temporária: o banco (data/) nasce vazio e some no fim.
  fs.cpSync(path.join(RAIZ, 'backend', 'app'), path.join(TEMP, 'backend', 'app'), { recursive: true, filter: (o) => !o.includes('__pycache__') })
  const python = pythonDoBackend()
  iniciar('smtp', python, [path.join(AQUI, 'fake_smtp.py'), String(PORTA_SMTP), CAIXA_EMAIL], { cwd: TEMP })
  const dist = path.join(RAIZ, 'frontend', 'dist')
  if (MODO_UNICO && !fs.existsSync(path.join(dist, 'index.html'))) throw new Error('QA_MODO=unica precisa do build: rode "npm run build" em frontend/')
  iniciar('backend', python, ['-m', 'uvicorn', 'app.main:app', '--host', MODO_UNICO ? '0.0.0.0' : '127.0.0.1', '--port', String(PORTA_API)], {
    cwd: path.join(TEMP, 'backend'),
    // Sem ADMIN_PASSWORD nem SECRET_KEY: como uma instalação nova da loja (assistente + chave automática).
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1', MONITOR_INTERVAL: '3', SNMP_METRICS_INTERVAL: '3', ADMIN_PASSWORD: '', SECRET_KEY: '',
      NETCABLE_DATA_DIR: path.join(TEMP, 'backend', 'data'), NETCABLE_STATIC_DIR: MODO_UNICO ? dist : path.join(TEMP, 'sem-interface') },
  })
  if (!MODO_UNICO) {
    iniciar('frontend', 'npx', ['vite'], {
      cwd: path.join(RAIZ, 'frontend'),
      env: { ...process.env, NETCABLE_API_PROXY: `http://127.0.0.1:${PORTA_API}`, NETCABLE_DEV_PORT: String(PORTA_WEB) },
    })
  }
  await aguardarUrl(`${API}/health`)
  await aguardarUrl(WEB)
}

// Código TOTP (RFC 6238) do app autenticador, para testar a verificação em duas etapas.
function totp(segredo, deslocamento = 0) {
  const alfabeto = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'
  const bits = [...segredo.replace(/=+$/, '').toUpperCase()].map(c => alfabeto.indexOf(c).toString(2).padStart(5, '0')).join('')
  const chave = Buffer.from(bits.match(/.{8}/g).map(b => parseInt(b, 2)))
  const msg = Buffer.alloc(8)
  msg.writeBigUInt64BE(BigInt(Math.floor(Date.now() / 30000) + deslocamento))
  const h = crypto.createHmac('sha1', chave).update(msg).digest()
  const o = h[h.length - 1] & 15
  return String((h.readUInt32BE(o) & 0x7fffffff) % 1e6).padStart(6, '0')
}

// ----------------------------------------------------------------------------- dados de exemplo
async function api(metodo, caminho, corpo, token) {
  const r = await fetch(`${API}${caminho}`, {
    method: metodo,
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: corpo ? JSON.stringify(corpo) : undefined,
  })
  const dados = await r.json().catch(() => ({}))
  if (!r.ok) throw new Error(`${metodo} ${caminho} -> ${r.status} ${JSON.stringify(dados)}`)
  return dados
}
async function login(usuario, senha) {
  const r = await fetch(`${API}/login`, { method: 'POST', body: new URLSearchParams({ username: usuario, password: senha }) })
  return (await r.json()).access_token
}

const MAPA = {
  equipamentos: [
    { id: 'r1', nome: 'Rack QA', ip: 'Sem IP', tipo: 'Rack', status: 'visual', monitorMode: 'visual', posX: 0, posY: 0, width: 440, height: 384, alturaU: 12 },
    { id: 'fw', nome: 'Firewall QA', ip: '127.0.0.1', tipo: 'Firewall', status: 'offline', posX: 0, posY: 0, width: 380, height: 28, rackId: 'r1', rackU: 12, alturaU: 1 },
    { id: 'sw', nome: 'Switch QA', ip: '127.0.0.1', tipo: 'Switch Gerenciável', status: 'offline', posX: 0, posY: 0, width: 380, height: 28, rackId: 'r1', rackU: 10, alturaU: 1 },
    { id: 'nas', nome: 'NAS QA', ip: '127.0.0.1', tipo: 'Storage/NAS', status: 'offline', posX: 0, posY: 0, width: 380, height: 56, rackId: 'r1', rackU: 6, alturaU: 2 },
    { id: 'ap', nome: 'AP Solto', ip: '192.0.2.50', tipo: 'Roteador', status: 'offline', posX: 620, posY: 40, width: 200, height: 80 },
  ],
  conexoes: [{ id: 'e1', source: 'sw', target: 'ap', sourceHandle: 'right', targetHandle: 'left' }],
}

let TOKEN, PID
async function popularDados() {
  TOKEN = await login(ADMIN.usuario, ADMIN.senha)
  await api('POST', '/usuarios', { username: 'qa-viewer', senha: 'qa-viewer-123', papel: 'visualizador' }, TOKEN)
  PID = (await api('POST', '/projetos?nome=QA%20Homelab', null, TOKEN)).id
  await api('POST', `/projetos/${PID}/salvar`, MAPA, TOKEN)
  await esperar(4000) // primeiro ciclo do monitor
}
async function restaurarMapa() {
  await api('POST', `/projetos/${PID}/salvar`, MAPA, TOKEN)
  for (const m of await api('GET', '/modelos', null, TOKEN)) await api('DELETE', `/modelos/${m.id}`, null, TOKEN).catch(() => {})
}

// ----------------------------------------------------------------------------- resultados
const R = { cenarios: [], achados: [], inicio: new Date() }
let numPrint = 0
async function print(page, nome) {
  const arquivo = `${String(++numPrint).padStart(3, '0')}-${nome.replace(/[^\w-]+/g, '_').slice(0, 50)}.png`
  try { await page.screenshot({ path: path.join(PRINTS, arquivo) }); return `prints/${arquivo}` } catch { return null }
}

// Observa erros "de fundo" em qualquer aba: exceções JS, erros no console, respostas 5xx e textos sem tradução.
function vigiar(ctx, onde, acoes = []) {
  const registrar = (tipo, msg) => R.achados.push({ tipo, onde, msg, passos: acoes.slice(-6) })
  ctx.on('page', (page) => {
    page.on('pageerror', e => registrar('bug', `Exceção JavaScript: ${e.message}`))
    page.on('console', m => {
      const t = m.text()
      if (t.includes('[i18n] tradução faltando')) registrar('traducao', t.replace('[i18n] ', ''))
      else if (m.type() === 'error' && !/status of 4\d\d/.test(t)) registrar('bug', `Erro no console: ${t.slice(0, 300)}`)
    })
    page.on('response', r => { if (r.status() >= 500) registrar('bug', `HTTP ${r.status()} em ${new URL(r.url()).pathname}`) })
  })
}

// Roda em toda página nova; na página em branco inicial o localStorage é proibido (ignora).
const DEFINIR_IDIOMA = (i) => { try { localStorage.setItem('netcable_idioma', i) } catch { /* about:blank */ } }

async function novoContexto(idioma = 'pt', onde = '') {
  const ctx = await navegador.newContext({ viewport: { width: 1400, height: 880 } })
  await ctx.addInitScript(DEFINIR_IDIOMA, idioma)
  vigiar(ctx, onde)
  return ctx
}

async function entrar(page, usuario = ADMIN.usuario, senha = ADMIN.senha) {
  await page.goto(WEB + '/')
  await page.fill('input[type=text]', usuario)
  await page.fill('input[type=password]', senha)
  await page.click('button[type=submit]')
  await page.waitForURL(/projects/, { timeout: 15000 })
}

const existe = (page, sel, timeout = 6000) => page.waitForSelector(sel, { timeout }).then(() => true).catch(() => false)

async function cenario(nome, fn) {
  if (RAPIDO && fn.lento) return
  const c = { nome, checks: [], erro: null, prints: [], ms: 0 }
  R.cenarios.push(c)
  const inicio = Date.now()
  const ctx = await novoContexto('pt', nome)
  const page = await ctx.newPage()
  page.on('dialog', d => d.accept())
  const ok = async (cond, msg) => {
    c.checks.push({ ok: !!cond, msg })
    if (!cond) c.prints.push(await print(page, `falha-${nome}-${msg}`))
  }
  try {
    await fn({ page, ctx, ok })
  } catch (e) {
    c.erro = e.message.split('\n')[0]
    c.prints.push(await print(page, `erro-${nome}`))
  } finally {
    c.ms = Date.now() - inicio
    await ctx.close()
  }
  const falhas = c.checks.filter(x => !x.ok).length + (c.erro ? 1 : 0)
  log(`${falhas ? '❌' : '✅'} ${nome} (${c.checks.length} verificações, ${(c.ms / 1000).toFixed(1)}s)`)
}

const titulo = (page, id) => page.locator(`.react-flow__node[data-id="${id}"] .rack-equip`).getAttribute('title')
async function yDoU(page, rackId, u) {
  const us = Number((await page.locator(`.react-flow__node[data-id="${rackId}"] .rack-badge`).innerText()).replace('U', ''))
  const b = await page.locator(`.react-flow__node[data-id="${rackId}"] .rack-trilho-esq .rack-trilho-u`).nth(us - u).boundingBox()
  return b.y + b.height / 2
}
async function arrastar(page, seletorOuBox, x, y) {
  const b = typeof seletorOuBox === 'string' ? await page.locator(seletorOuBox).boundingBox() : seletorOuBox
  const sx = b.x + b.width * 0.55, sy = b.y + Math.min(b.height / 2, 12)
  await page.mouse.move(sx, sy); await page.mouse.down()
  await page.mouse.move((sx + x) / 2, (sy + y) / 2, { steps: 5 })
  await page.mouse.move(x, y, { steps: 8 }); await page.mouse.up()
  await page.waitForTimeout(400)
}
async function abrirEditor(page) {
  await page.goto(`${WEB}/editor/${PID}`)
  await page.waitForSelector('.rack-gabinete')
  await page.waitForTimeout(700)
}

// ----------------------------------------------------------------------------- roteiros
async function roteiros() {
  await cenario('Login e idioma', async ({ page, ok }) => {
    await page.evaluate(() => localStorage.clear()).catch(() => {})
    await page.goto(WEB + '/')
    await page.evaluate(() => { localStorage.removeItem('netcable_idioma') })
    await page.reload()
    // O init script define PT; aqui forçamos o padrão (sem escolha) para conferir o inglês.
    await page.evaluate(() => localStorage.removeItem('netcable_idioma'))
    await page.goto(WEB + '/?padrao')
    await page.click('button:has-text("EN")')
    await ok(await existe(page, 'button:has-text("Sign in")'), 'login em inglês')
    await page.fill('input[type=text]', 'ninguem'); await page.fill('input[type=password]', 'errada')
    await page.click('button[type=submit]')
    await ok(await existe(page, 'text=Incorrect username or password'), 'erro da API traduzido para inglês')
    await page.click('button:has-text("PT")')
    await ok(await existe(page, 'button:has-text("Entrar")'), 'troca para português na hora')
    await page.fill('input[type=text]', ADMIN.usuario); await page.fill('input[type=password]', ADMIN.senha)
    await page.click('button[type=submit]')
    await ok(await page.waitForURL(/projects/, { timeout: 10000 }).then(() => true).catch(() => false), 'login com senha correta')
    await ok(await existe(page, 'text=QA Homelab'), 'mapa aparece na lista de projetos')
  })

  await cenario('Adicionar equipamento solto (rapidez)', async ({ page, ok }) => {
    await entrar(page); await abrirEditor(page)
    const antes = await page.locator('.react-flow__node').count()
    await page.click('button:has-text("Adicionar")')
    await page.selectOption('select[aria-label="Tipo de Equipamento"]', 'Servidor')
    await page.fill('input[placeholder="Ex: Switch Andar 1"]', 'Servidor QA')
    await page.fill('input[placeholder="Ex: 192.168.0.10"]', '127.0.0.1')
    await page.click('button:has-text("Testar")')
    await ok(await existe(page, 'text=/Online! Resposta em/', 5000), 'botão "Testar" responde online')
    const t0 = Date.now()
    await page.click('div[style*="z-index: 1000"] button:has-text("Adicionar") >> nth=-1')
    const apareceu = await existe(page, '.react-flow__node:has-text("Servidor QA")', 8000)
    await ok(apareceu, 'equipamento aparece no mapa')
    await ok(Date.now() - t0 < 4000, `aparece rápido (${((Date.now() - t0) / 1000).toFixed(1)}s, limite 4s)`)
    await ok(await page.locator('.react-flow__node').count() === antes + 1, 'exatamente um nó novo')
  })

  await cenario('Racks: montar, mover e salvar', async ({ page, ok }) => {
    await restaurarMapa()
    await entrar(page); await abrirEditor(page)
    const rack = await page.locator('.react-flow__node[data-id="r1"]').boundingBox()
    await arrastar(page, '.react-flow__node[data-id="sw"]', rack.x + rack.width / 2, await yDoU(page, 'r1', 8) - 4)
    await ok((await titulo(page, 'sw')).includes('U8'), 'switch encaixa no U8 ao arrastar')
    await arrastar(page, '.react-flow__node[data-id="ap"]', rack.x + rack.width / 2, await yDoU(page, 'r1', 3))
    await ok(await page.locator('.react-flow__node[data-id="ap"] .rack-equip').count() === 1, 'equipamento solto é montado ao soltar no rack')
    await page.keyboard.press('Control+s')
    await ok(await existe(page, 'text=Projeto salvo com sucesso!'), 'salvar (Ctrl+S)')
    await page.reload(); await page.waitForSelector('.rack-gabinete'); await page.waitForTimeout(600)
    await ok((await titulo(page, 'sw')).includes('U8') && await page.locator('.react-flow__node[data-id="ap"] .rack-equip').count() === 1, 'posições continuam após recarregar')
    await ok(await page.locator('.react-flow__edge').count() === 1, 'cabo continua ligado')
  })

  await cenario('Modelos e cabos por porta', async ({ page, ok }) => {
    await restaurarMapa()
    await entrar(page); await abrirEditor(page)
    await page.locator('button:has(svg.lucide-settings)').click()
    await page.click('text=Modelos de equipamento')
    await page.click('button:has-text("Novo modelo")')
    await page.fill('input[placeholder="Ex: Grandstream GWN7003"]', 'Firewall QA 4+2')
    await page.selectOption('select[aria-label="Tipo do modelo"]', 'Firewall')
    await page.fill('input[aria-label="Portas RJ45"]', '4')
    await page.fill('input[aria-label="Portas SFP"]', '2')
    await page.fill('input[aria-label="Prefixo das portas"]', 'eth')
    await page.click('button:has-text("Salvar modelo")')
    await ok(await existe(page, 'td:has-text("4× RJ45 + 2× SFP")'), 'modelo criado na biblioteca')
    await page.locator('h2:has-text("Modelos de equipamento") + button').click()
    await page.locator('.react-flow__node[data-id="fw"] .rack-equip-id').click()
    await page.selectOption('select[aria-label="Modelo"]', { label: 'Firewall QA 4+2 — Firewall, 1U, 4× RJ45 + 2× SFP' })
    await page.click('button:has-text("Salvar Alterações")')
    await page.waitForTimeout(500)
    await ok(await page.locator('.react-flow__node[data-id="fw"] .porta-rj45').count() === 4, 'frente com 4 portas RJ45 do modelo')
    const ligar = async (a, pa, b, pb) => {
      const x = await page.locator(`.react-flow__node[data-id="${a}"] .handle-porta[data-handleid="${pa}"]`).boundingBox()
      const y = await page.locator(`.react-flow__node[data-id="${b}"] .handle-porta[data-handleid="${pb}"]`).boundingBox()
      await page.mouse.move(x.x + x.width / 2, x.y + x.height / 2); await page.mouse.down()
      await page.mouse.move(x.x + 50, x.y - 40, { steps: 5 })
      await page.mouse.move(y.x + y.width / 2, y.y + y.height / 2, { steps: 10 }); await page.mouse.up()
      await page.waitForTimeout(700)
    }
    await ligar('sw', 'p:12', 'fw', 'p:3')
    await ok(await page.locator('.react-flow__edge').count() === 2, 'cabo porta→porta criado')
    await ok((await page.locator('.react-flow__node[data-id="fw"] .porta-rj45').nth(2).getAttribute('title') || '').startsWith('eth3 →'), 'porta em uso mostra o destino')
    await ligar('sw', 'p:20', 'fw', 'p:3')
    await ok(await existe(page, 'text=/já tem um cabo conectado/'), 'porta ocupada recusa segundo cabo')
    await ligar('sw', 's:1', 'fw', 's:2')
    await ok(await page.locator('.react-flow__edge').count() === 3, 'cabo SFP criado após trocar o modelo')
    await page.click('button[title="Modo visualização (somente leitura)"]'); await page.waitForTimeout(400)
    await ok(await page.locator('.react-flow__edge').count() === 3, 'cabos por porta visíveis no modo visualização')
    await page.click('button:has-text("Editar")')
    await page.keyboard.press('Control+s')
    await ok(await existe(page, 'text=Projeto salvo com sucesso!'), 'salvar')
    const dados = await api('GET', `/projetos/${PID}/dados`, null, TOKEN)
    await ok(dados.conexoes.some(c => c.source_handle === 's:1' && c.target_handle === 's:2'), 'portas gravadas no servidor')
  })

  const publico = async ({ page, ctx, ok }) => {
    await restaurarMapa()
    await entrar(page); await abrirEditor(page)
    await page.click('button[title="Modo visualização (somente leitura)"]'); await page.waitForTimeout(300)
    await ok(await page.evaluate(() => [...document.querySelectorAll('.react-flow__handle')].every(h => getComputedStyle(h).opacity === '0')), 'modo visualização esconde os pontos de conexão')
    await page.click('button:has-text("Editar")')
    await page.locator('button:has(svg.lucide-settings)').click()
    await page.click('text=Copiar Link Público')
    await ok(await existe(page, 'text=Link público copiado!'), `copiar link (${ipLocal ? 'via http://IP' : 'localhost'})`)
    const tok = (await api('GET', `/projetos/${PID}/compartilhar`, null, TOKEN)).token
    const tv = await ctx.newPage()
    await tv.goto(`${WEB}/share/${tok}`)
    await ok(await existe(tv, '.rack-gabinete'), 'página pública desenha o rack')
    const h1 = await tv.locator('text=/Atualizado às/').innerText().catch(() => '')
    await tv.waitForTimeout(11000)
    const h2 = await tv.locator('text=/Atualizado às/').innerText().catch(() => '')
    await ok(h1 && h1 !== h2, 'página pública atualiza sozinha')
    await api('DELETE', `/projetos/${PID}/compartilhar`, null, TOKEN)
    await ok(await existe(tv, 'text=/inválido ou foi revogado/', 15000), 'TV aberta sai do ar ao revogar o link')
  }
  publico.lento = true
  await cenario('Modo visualização e link público', publico)

  await cenario('Usuários e papéis', async ({ page, ok }) => {
    await entrar(page, 'qa-viewer', 'qa-viewer-123')
    await ok(await page.locator('text=Criar Novo Projeto').count() === 0, 'visualizador não vê "Criar Novo Projeto"')
    await abrirEditor(page)
    await ok(await page.locator('text=Somente visualização').count() === 1, 'editor em somente leitura para o visualizador')
    await ok(await page.locator('button:has-text("Salvar")').count() === 0, 'sem botão Salvar')
    const tokViewer = await login('qa-viewer', 'qa-viewer-123')
    const r = await fetch(`${API}/projetos/${PID}/salvar`, { method: 'POST', headers: { Authorization: `Bearer ${tokViewer}`, 'Content-Type': 'application/json' }, body: JSON.stringify(MAPA) })
    await ok(r.status === 403, `API recusa salvar para visualizador (HTTP ${r.status})`)
  })

  await cenario('E-mail (SMTP falso)', async ({ page, ok }) => {
    await entrar(page)
    await page.locator('button[title="Configurações"]').click()
    await page.click('text=E-mail (SMTP)')
    await page.fill('input[placeholder="smtp.seudominio.com"]', '127.0.0.1')
    await page.fill('input[type=number]', String(PORTA_SMTP))
    await page.locator('label:has-text("Segurança") select').selectOption('nenhuma')
    await page.fill('input[placeholder="NetCable <noc@seudominio.com>"]', 'NetCable QA <qa@netcable.local>')
    await page.fill('input[placeholder="seu@email.com"]', 'qa@netcable.local')
    await page.click('button:has-text("Salvar e testar")')
    await ok(await existe(page, 'text=/E-mail de teste enviado/', 10000), 'e-mail de teste enviado')
    await esperar(800)
    const emails = fs.existsSync(CAIXA_EMAIL) ? fs.readFileSync(CAIXA_EMAIL, 'utf8').trim().split('\n').filter(Boolean) : []
    await ok(emails.length >= 1, `SMTP recebeu o e-mail (${emails.length})`)
  })

  await cenario('Backup, exportar e importar', async ({ page, ok }) => {
    await restaurarMapa()
    await entrar(page)
    await page.locator('button[title="Configurações"]').click()
    await page.click('button:has-text("Backup")')
    await ok(await existe(page, 'text=Backup automático diário'), 'tela de backup abre')
    await page.click('button:has-text("Fazer backup agora")')
    await ok(await existe(page, 'text=/Backup criado: netcable-backup-/', 15000), 'backup manual criado')
    await ok(await page.locator('[role=dialog] span:has-text("netcable-backup-")').count() >= 1, 'arquivo aparece na lista')
    const [download] = await Promise.all([page.waitForEvent('download', { timeout: 10000 }), page.locator('[role=dialog] button[title="Baixar"]').first().click()])
    const zip = path.join(PASTA, 'backup-qa.zip')
    await download.saveAs(zip)
    await ok(fs.statSync(zip).size > 1000, `download do .zip (${fs.statSync(zip).size} bytes)`)
    await page.locator('[role=dialog] button[aria-label="Fechar"]').click()

    const antes = await page.locator('h3').count()
    const [exportado] = await Promise.all([page.waitForEvent('download', { timeout: 10000 }), page.locator('button[title="Exportar mapa (.json)"]').first().click()])
    const json = path.join(PASTA, 'mapa-qa.json')
    await exportado.saveAs(json)
    const mapa = JSON.parse(fs.readFileSync(json, 'utf8'))
    await ok(mapa.formato === 'netcable-mapa' && mapa.equipamentos.length >= 4, 'mapa exportado no formato novo')
    await page.locator('input[type=file][accept=".json,.zip"]').setInputFiles(json)
    await ok(await existe(page, 'text=/importado\\(s\\) como projeto novo/', 10000), 'importação cria projeto novo')
    await page.waitForTimeout(800)
    await ok(await page.locator('h3').count() === antes + 1, 'novo card aparece na lista')
    await page.locator('input[type=file][accept=".json,.zip"]').setInputFiles(zip)
    await ok(await existe(page, 'text=/importado\\(s\\) como projeto novo/', 10000), 'importar o .zip do backup recupera os mapas')
    // limpa os projetos extras para não afetar os próximos cenários
    for (const p of await api('GET', '/projetos', null, TOKEN)) if (p.id !== PID) await api('DELETE', `/projetos/${p.id}`, null, TOKEN)
  })

  await cenario('Alertas inteligentes: uplink, manutenção e canais', async ({ page, ok }) => {
    // Servidor HTTP local fazendo papel do ntfy.
    const recebidos = []
    const srv = http.createServer((req, res) => {
      let corpo = ''
      req.on('data', c => { corpo += c })
      req.on('end', () => { recebidos.push({ url: req.url, corpo, prioridade: req.headers.priority }); res.end('ok') })
    })
    await new Promise(r => srv.listen(0, '127.0.0.1', r))
    try {
      const cam = { id: 'cam', nome: 'Câmera QA', ip: '192.0.2.51', tipo: 'PC', status: 'offline', posX: 900, posY: 40, width: 200, height: 80 }
      await api('POST', `/projetos/${PID}/salvar`, { equipamentos: [...MAPA.equipamentos, cam], conexoes: [...MAPA.conexoes, { id: 'e2', source: 'ap', target: 'cam', sourceHandle: 'right', targetHandle: 'left' }] }, TOKEN)
      await entrar(page); await abrirEditor(page)
      await page.locator('.react-flow__node[data-id="sw"] .rack-equip-id').click()
      await page.click('button:has-text("Usar como raiz e calcular uplinks pelos cabos")')
      await ok(await existe(page, 'text=/uplink\\(s\\) definidos/'), 'uplinks calculados pelos cabos')
      await page.keyboard.press('Control+s')
      await page.waitForTimeout(1200)
      const dados = await api('GET', `/projetos/${PID}/dados`, null, TOKEN)
      const dep = Object.fromEntries(dados.equipamentos.map(e => [e.id, e.depende_de]))
      await ok(dep.ap === 'sw' && dep.cam === 'ap', `uplinks salvos (ap→${dep.ap}, cam→${dep.cam})`)
      await ok(await existe(page, '.react-flow__node[data-id="cam"] .status-inalcancavel', 12000), 'câmera atrás do AP offline aparece como inalcançável (âmbar)')
      await page.locator('.react-flow__node[data-id="cam"]').click()
      const uplink = await page.locator('select[aria-label="Depende de (uplink)"] option:checked').innerText()
      await ok(uplink.includes('AP Solto'), `modal mostra o uplink (${uplink})`)
      await page.click('button:has-text("Silenciar")')
      await ok(await existe(page, 'text=/Alertas de Câmera QA silenciados/'), 'manutenção do equipamento')
      await page.locator('h2:has-text("Editar Equipamento") + button').click()
      await ok(await existe(page, '.react-flow__node[data-id="cam"] .node-manutencao', 8000), 'ícone de manutenção no mapa')

      await page.click('button[title="Manutenção: silenciar os alertas deste mapa"]')
      await page.click('[role=menuitem]:has-text("1 h")')
      await ok(await existe(page, 'button[aria-pressed="true"]:has-text("até")'), 'mapa inteiro em manutenção (botão mostra "até HH:MM")')
      await page.locator('button[aria-pressed="true"]:has-text("até")').click()
      await page.click('[role=menuitem]:has-text("Encerrar manutenção")')
      await ok(await existe(page, 'button[title="Manutenção: silenciar os alertas deste mapa"]'), 'manutenção do mapa encerrada')

      await page.goto(`${WEB}/projects`)
      await page.locator('button[title="Configurações"]').click()
      await page.click('button:has-text("Canais de alerta")')
      await page.fill('input[placeholder="https://ntfy.sh/meu-topico-secreto"]', `http://127.0.0.1:${srv.address().port}/qa-topico`)
      await page.click('[role=dialog] button[type=submit]')
      await ok(await existe(page, 'text=Canais de alerta salvos.'), 'canais salvos')
      await page.locator('[role=dialog] button:has-text("Testar")').nth(1).click()
      await ok(await existe(page, 'text=Mensagem de teste enviada.', 10000), 'teste do ntfy enviado')
      await ok(recebidos.some(r => r.url === '/qa-topico' && r.corpo.includes('NetCable')), `ntfy recebeu a mensagem (${recebidos.length})`)
    } finally {
      srv.close()
      await api('PUT', '/config/alertas', { ntfy_url: '' }, TOKEN).catch(() => {})
      await api('DELETE', `/projetos/${PID}/manutencao?equipamento_id=cam`, null, TOKEN).catch(() => {})
      await restaurarMapa()
    }
  })

  await cenario('Descoberta da rede', async ({ page, ok }) => {
    await restaurarMapa()
    await entrar(page); await abrirEditor(page)
    await page.click('button[title="Descobrir equipamentos na rede"]')
    await ok(await existe(page, '[role=dialog] input[aria-label="Faixa de IPs"]'), 'tela de descoberta abre')
    await page.fill('input[aria-label="Faixa de IPs"]', '8.8.8.0/24')
    await page.click('[role=dialog] button[type=submit]')
    await ok(await existe(page, 'text=/redes privadas/'), 'recusa faixa pública')
    // Loopback: rápido e sempre local (o resultado depende do sistema; o fluxo é o que importa).
    await page.fill('input[aria-label="Faixa de IPs"]', '127.0.0.1-127.0.0.4')
    await page.click('[role=dialog] button[type=submit]')
    await ok(await existe(page, 'text=/encontrado\\(s\\) em|Nenhum equipamento respondeu/', 20000), 'varredura termina')
    const linhas = await page.locator('[role=dialog] tbody tr').count()
    if (linhas > 0) {
      const antes = await page.locator('.react-flow__node').count()
      await page.locator('[role=dialog] thead input[type=checkbox]').check()
      await page.locator('[role=dialog] button:has-text("ao mapa")').click()
      await page.waitForTimeout(600)
      await ok(await page.locator('.react-flow__node').count() === antes + linhas, `${linhas} equipamento(s) descoberto(s) adicionados ao mapa`)
    }
  })

  // Só com um agente SNMP simulado (snmpsim): QA_SNMPSIM=127.0.0.1:11161 e QA_PYTHON com pysnmp.
  if (process.env.QA_SNMPSIM) await cenario('Métricas SNMP (agente simulado)', async ({ page, ok }) => {
    const [host, porta] = process.env.QA_SNMPSIM.split(':')
    const sw = { id: 'snmp', nome: 'Switch SNMP', ip: host, tipo: 'Switch Gerenciável', status: 'offline', posX: 0, posY: 0, width: 380, height: 28,
      rackId: 'r1', rackU: 8, alturaU: 1, monitorMode: 'snmpv3', modeloId: null,
      monitorConfig: { username: 'netcable', authProtocol: 'SHA', authPassword: 'authpass123', privProtocol: 'AES', privPassword: 'privpass123', port: Number(porta), context: 'public' } }
    const modelo = await api('POST', '/modelos', { nome: 'Lab 4p', tipo: 'Switch Gerenciável', altura_u: 1, portas_rj45: 4, portas_sfp: 0, prefixo_porta: 'ge' }, TOKEN)
    await api('POST', `/projetos/${PID}/salvar`, { ...MAPA, equipamentos: [...MAPA.equipamentos, { ...sw, modeloId: modelo.id }] }, TOKEN)
    await entrar(page); await abrirEditor(page)
    await ok(await existe(page, '.react-flow__node[data-id="snmp"] .rack-equip-ping:has-text("47°")', 30000), 'temperatura (47°) aparece no rack')
    await ok(await existe(page, '.react-flow__node[data-id="snmp"] .porta-rj45.sem-link', 8000), 'porta 3 sem link aparece apagada (LED real)')
    // O tráfego precisa de duas coletas (a taxa é a variação dos contadores).
    let dica = ''
    for (let i = 0; i < 20 && !dica.includes('Mb/s'); i++) {
      dica = await page.locator('.react-flow__node[data-id="snmp"] .porta-rj45').first().getAttribute('title')
      if (!dica.includes('Mb/s')) await page.waitForTimeout(1000)
    }
    await ok(dica.includes('ge-0/0/1 (uplink firewall)') && dica.includes('Mb/s'), `tooltip da porta 1 com nome, descrição e tráfego (${dica.split('\n').join(' | ')})`)
    await print(page, 'snmp-rack')
    await page.locator('.react-flow__node[data-id="snmp"] .rack-equip-id').click()
    await page.click('button:has-text("Ver métricas")')
    await ok(await existe(page, '[role=dialog][aria-label="Métricas SNMP"] >> text=47 °C'), 'modal de métricas com temperatura')
    await ok(await existe(page, '[role=dialog] td:has-text("uplink firewall")'), 'tabela de portas com descrição')
    await ok(await page.locator('[role=dialog] svg[role=img]').count() >= 3, 'gráficos de temperatura, CPU/memória e tráfego')
    await print(page, 'snmp-metricas')
    await page.locator('[role=dialog] button[aria-label="Fechar"]').click()
    await restaurarMapa()
  })

  await cenario('Atalhos entre mapas', async ({ page, ok }) => {
    await restaurarMapa()
    const filial = (await api('POST', '/projetos?nome=Filial%20QA', null, TOKEN)).id
    try {
      await api('POST', `/projetos/${filial}/salvar`, { equipamentos: [
        { id: 'fq1', nome: 'Roteador Filial', ip: '192.0.2.77', tipo: 'Roteador', status: 'offline', posX: 0, posY: 0, width: 200, height: 80 },
      ], conexoes: [] }, TOKEN)
      await entrar(page); await abrirEditor(page)
      await page.click('button:has-text("Adicionar")')
      await page.selectOption('select[aria-label="Tipo de Equipamento"]', 'Atalho de mapa')
      await page.selectOption('select[aria-label="Mapa de destino"]', String(filial))
      await ok((await page.inputValue('input[placeholder="Ex: Switch Andar 1"]')) === 'Filial QA', 'nome do atalho preenchido com o nome do mapa')
      await page.click('div[style*="z-index: 1000"] button:has-text("Adicionar") >> nth=-1')
      await ok(await existe(page, '.react-flow__node .no-atalho:has-text("Filial QA")'), 'atalho aparece no mapa')
      await page.keyboard.press('Control+s'); await page.waitForTimeout(1200)
      await ok(await existe(page, '.react-flow__node .no-atalho.atalho-alerta', 10000), 'atalho fica vermelho: há equipamento offline na filial')
      await page.locator('.react-flow__node .no-atalho').dblclick()
      await page.waitForURL(`**/editor/${filial}`, { timeout: 8000 }).catch(() => {})
      await ok(page.url().endsWith(`/editor/${filial}`), 'duplo clique abre o mapa da filial')
      await ok(await existe(page, '.react-flow__node:has-text("Roteador Filial")'), 'mapa da filial carregado')
    } finally {
      await api('DELETE', `/projetos/${filial}`, null, TOKEN).catch(() => {})
      await restaurarMapa()
    }
  })

  await cenario('Histórico, latência e diagnóstico', async ({ page, ok }) => {
    await entrar(page); await abrirEditor(page)
    await page.locator('button:has(svg.lucide-settings)').click()
    await page.click('text=Histórico')
    await ok(await existe(page, 'text=Switch QA'), 'aba disponibilidade lista equipamentos')
    await page.locator('tr:has-text("Switch QA")').click()
    await ok(await existe(page, 'svg[role=img]'), 'gráfico de latência abre')
    await page.click('button:has-text("Eventos")')
    await ok(await existe(page, 'th:has-text("Horário")', 4000) || await existe(page, 'text=Ainda não há verificações registradas.', 1000), 'aba eventos abre')
    await page.locator('h2:has-text("Histórico de disponibilidade") + button').click()
    await page.locator('button:has(svg.lucide-settings)').click()
    await page.click('text=Diagnóstico')
    await ok(await existe(page, 'text=Monitor no servidor'), 'diagnóstico abre')
  })

  await cenario('Barra: cabos entre portas, busca e destaque', async ({ page, ok }) => {
    await restaurarMapa()
    await api('POST', `/projetos/${PID}/salvar`, { ...MAPA, conexoes: [...MAPA.conexoes, { id: 'p1', source: 'sw', target: 'fw', sourceHandle: 'p:1', targetHandle: 'p:1' }] }, TOKEN)
    await entrar(page); await abrirEditor(page)
    await ok(await page.locator('.react-flow__edge').count() === 2, 'cabo entre portas desenhado')
    await page.click('button[title="Ocultar cabos entre portas"]'); await page.waitForTimeout(300)
    await ok(await page.locator('.react-flow__edge').count() === 1, 'botão oculta os cabos entre portas (o cabo lateral continua)')
    await ok((await page.locator('.react-flow__node[data-id="fw"] .porta-rj45').first().getAttribute('class')).includes('em-uso'), 'porta continua marcada como em uso')
    await page.reload(); await page.waitForSelector('.rack-gabinete'); await page.waitForTimeout(600)
    await ok(await page.locator('button[title="Mostrar cabos entre portas"]').count() === 1 && await page.locator('.react-flow__edge').count() === 1, 'preferência lembrada após recarregar')
    await page.locator('.react-flow__node[data-id="sw"] .rack-equip-id').hover(); await page.waitForTimeout(300)
    await ok(await page.locator('.react-flow__edge').count() === 2, 'passar o mouse no switch revela os cabos dele')
    await ok((await page.locator('.react-flow__node[data-id="nas"]').getAttribute('class')).includes('no-esmaecido'), 'equipamentos sem ligação ficam apagados')
    await page.mouse.move(5, 300); await page.waitForTimeout(300)
    await page.click('button[title="Mostrar cabos entre portas"]'); await page.waitForTimeout(300)
    await ok(await page.locator('.react-flow__edge').count() === 2, 'botão volta a mostrar os cabos')
    await page.keyboard.press('Control+k')
    await page.keyboard.type('NAS')
    await ok(await existe(page, '[role=option]:has-text("NAS QA")'), 'busca (Ctrl+K) encontra pelo nome')
    await page.keyboard.press('Enter')
    await ok(await existe(page, '.react-flow__node.no-destaque[data-id="nas"]', 3000), 'Enter centraliza e destaca o equipamento')
    await page.locator('input[aria-label="Buscar equipamento (Ctrl+K)"]').fill('192.0.2')
    await ok(await existe(page, '[role=option]:has-text("AP Solto")'), 'busca também encontra pelo IP')
  })

  await cenario('Alterações não salvas', async ({ page, ok }) => {
    await restaurarMapa()
    await entrar(page); await abrirEditor(page)
    await arrastar(page, '.react-flow__node[data-id="ap"]', 1100, 600)
    await ok((await page.locator('button:has-text("Salvar")').first().innerText()).includes('*'), 'botão vira "Salvar *"')
    page.removeAllListeners('dialog'); page.on('dialog', d => d.dismiss())
    await page.click('button[title="Voltar aos projetos"]'); await page.waitForTimeout(400)
    await ok(page.url().includes('/editor/'), 'aviso ao sair sem salvar (cancelado = continua no editor)')
  })

  await cenario('Verificação em duas etapas (2FA)', async ({ page, ok }) => {
    const usuario = { username: 'qa-2fa', senha: 'qa-2fa-senha-1' }
    const u = await api('POST', '/usuarios', { ...usuario, papel: 'editor' }, TOKEN)
    try {
      await entrar(page, usuario.username, usuario.senha)
      await page.click('button[title="Configurações"]')
      await page.click('button:has-text("Meu perfil e notificações")')
      await page.click('button:has-text("Ativar verificação em duas etapas")')
      await page.fill('input[aria-label="Senha Atual"]', usuario.senha)
      await page.click('button:has-text("Continuar")')
      await ok(await existe(page, 'img[alt="QR code da verificação em duas etapas"]'), 'QR code aparece')
      const segredo = (await page.locator('code').first().innerText()).trim()
      await page.fill('input[aria-label="Código de verificação"]', totp(segredo))
      await page.click('button:has-text("Ativar")')
      await ok(await existe(page, 'button:has-text("Já guardei")'), 'códigos de recuperação mostrados')
      await page.click('button:has-text("Já guardei")')
      const me = await api('GET', '/usuarios', null, TOKEN)
      await ok(me.find(x => x.id === u.id)?.totp_ativo, '2FA ativo no usuário')

      // Novo login: senha e depois o código (o próximo passo de 30 s, pois o atual já foi usado)
      await page.evaluate(() => localStorage.removeItem('netcable_token'))
      await page.goto(WEB + '/')
      await page.fill('input[type=text]', usuario.username)
      await page.fill('input[type=password]', usuario.senha)
      await page.click('button[type=submit]')
      await ok(await existe(page, 'text=Verificação em duas etapas'), 'login pede o código')
      await page.fill('input[aria-label="Código de verificação"]', '000000')
      await page.click('button:has-text("Verificar")')
      await ok(await existe(page, 'text=/Código de verificação incorreto/'), 'código errado é recusado')
      await page.fill('input[aria-label="Código de verificação"]', totp(segredo, 1))
      await page.click('button:has-text("Verificar")')
      await page.waitForURL(/projects/, { timeout: 15000 }).catch(() => {})
      await ok(page.url().includes('/projects'), 'entra com o código do app')
    } finally {
      await api('DELETE', `/usuarios/${u.id}`, null, TOKEN).catch(() => {})
    }
  })

  await cenario('Estou vendo e agenda de manutenção', async ({ page, ok }) => {
    await restaurarMapa()
    try {
      await entrar(page); await abrirEditor(page)
      await page.locator('.react-flow__node[data-id="ap"]').click()
      await ok(await existe(page, 'button:has-text("Estou vendo")', 10000), 'AP offline oferece "Estou vendo"')
      await page.fill('input[aria-label="Nota (opcional)"]', 'indo ao rack')
      await page.click('button:has-text("Estou vendo")')
      await ok(await existe(page, 'text=/Alerta reconhecido/'), 'reconhecimento confirmado')
      await ok(await existe(page, 'text=/está cuidando desde/'), 'modal mostra quem está cuidando')
      await page.locator('h2:has-text("Editar Equipamento") + button').click()
      await ok(await existe(page, '.react-flow__node[data-id="ap"] .node-reconhecido', 12000), 'olho de "reconhecido" no mapa')

      await page.click('button[title="Manutenção: silenciar os alertas deste mapa"]')
      await page.click('[role=menuitem]:has-text("Agendar / agenda")')
      await ok(await existe(page, '[role=dialog][aria-label="Agenda de manutenção"]'), 'agenda abre')
      await page.click('[role=dialog] button:has-text("Toda semana")')
      const domingo = page.locator('[role=group][aria-label="Dias da semana"] button').last()
      if (await domingo.getAttribute('aria-pressed') !== 'true') await domingo.click()
      await page.fill('[role=dialog] input[type=time]', '02:00')
      await page.fill('[role=dialog] input[type=number]', '2')
      await page.fill('[role=dialog] input[placeholder="ex.: atualização de firmware"]', 'QA semanal')
      await page.click('[role=dialog] button[type=submit]:has-text("Agendar")')
      await ok(await existe(page, '[role=dialog] >> text=/QA semanal/'), 'janela semanal aparece na agenda')
      const lista = await api('GET', `/projetos/${PID}/manutencao`, null, TOKEN)
      const semanal = (lista.manutencoes || lista).find?.(m => m.motivo === 'QA semanal')
      await ok(semanal?.recorrencia?.hora === '02:00', `salva toda semana às 02:00 (${JSON.stringify(semanal?.recorrencia)})`)
      await print(page, 'agenda-manutencao')
    } finally {
      await api('DELETE', `/projetos/${PID}/equipamentos/ap/reconhecer`, null, TOKEN).catch(() => {})
      const lista = await api('GET', `/projetos/${PID}/manutencao`, null, TOKEN).catch(() => [])
      for (const m of (lista.manutencoes || lista || [])) await api('DELETE', `/projetos/${PID}/manutencao/${m.id}`, null, TOKEN).catch(() => {})
    }
  })

  await cenario('Página de status e incidentes', async ({ page, ctx, ok }) => {
    await restaurarMapa()
    try {
      await entrar(page); await abrirEditor(page)
      await page.locator('button:has(svg.lucide-settings)').first().click()
      await page.click('button:has-text("Página de status pública")')
      await page.click('[role=dialog] button:has-text("Ativar página de status")')
      const campoLink = page.locator('[role=dialog] input[aria-label="Endereço da página"]')
      await campoLink.waitFor({ timeout: 8000 })
      const link = await campoLink.inputValue()
      await ok(/\/status\/[\w-]{20,}$/.test(link), `endereço da página gerado (${link.replace(/\/status\/.*/, '/status/…')})`)
      await page.click('[role=dialog] button:has-text("Incidentes")')
      await page.click('[role=dialog] button:has-text("Novo incidente")')
      await page.fill('input[aria-label="Título do incidente"]', 'Lentidão no link QA')
      await page.fill('textarea[aria-label="Mensagem do incidente"]', 'Estamos investigando com a operadora.')
      await page.locator('[role=dialog] fieldset label:has-text("AP Solto") input').check()
      await page.click('[role=dialog] button:has-text("Publicar incidente")')
      await ok(await existe(page, 'text=Incidente publicado na página de status.'), 'incidente publicado')

      const publica = await ctx.newPage()
      await publica.goto(link)
      await ok(await existe(publica, 'text=Lentidão no link QA'), 'incidente aparece na página pública')
      await ok(await existe(publica, 'text=Afetados: AP Solto'), 'serviço afetado listado pelo nome')
      const texto = await publica.locator('body').innerText()
      await ok(!texto.includes('127.0.0.1') && !texto.includes('192.0.2.50'), 'página pública não mostra IPs')
      await ok(await publica.locator('[role=list][aria-label^="Disponibilidade diária"]').count() >= 3, 'barras de disponibilidade dos serviços')
      await print(publica, 'pagina-status-incidente')

      await page.selectOption('[role=dialog] select[aria-label="Nova situação"]', 'resolvido')
      await page.fill('[role=dialog] input[aria-label="Atualização do incidente"]', 'Link normalizado.')
      await page.click('[role=dialog] button[aria-label="Publicar atualização"]')
      await ok(await existe(page, 'text=Atualização publicada.'), 'atualização publicada')
      await publica.reload()
      await ok(await existe(publica, 'article >> text=Link normalizado.'), 'página pública mostra a resolução')
      await publica.close()
    } finally {
      for (const i of await api('GET', `/projetos/${PID}/incidentes`, null, TOKEN).catch(() => [])) await api('DELETE', `/projetos/${PID}/incidentes/${i.id}`, null, TOKEN).catch(() => {})
      await api('DELETE', `/projetos/${PID}/status-publico`, null, TOKEN).catch(() => {})
    }
  })

  await cenario('Escalonamento e login pelo diretório (LDAP)', async ({ page, ctx, ok }) => {
    try {
      await entrar(page)
      await page.click('button[title="Configurações"]')
      await page.click('button:has-text("Canais de alerta")')
      await page.selectOption('[role=dialog] select[aria-label="Escalar depois de"]', '30')
      await page.fill('[role=dialog] input[aria-label="E-mails de quem recebe"]', 'coordenador@qa.local')
      await page.click('[role=dialog] button[type=submit]')
      await ok(await existe(page, 'text=Canais de alerta salvos.'), 'escalonamento salvo')
      const canais = await api('GET', '/config/alertas', null, TOKEN)
      await ok(canais.escalar_min === 30 && canais.escalar_emails === 'coordenador@qa.local', `escalonamento guardado (${canais.escalar_min} min)`)
      await page.locator('[role=dialog] button[aria-label="Fechar"]').click()

      await page.click('button[title="Configurações"]')
      await page.click('button:has-text("Diretório (LDAP/AD)")')
      await page.locator('[role=dialog] label:has-text("Permitir login pelo diretório") input').check()
      await page.fill('[role=dialog] input[aria-label="Servidor LDAP"]', 'ldap://127.0.0.1:1')
      await page.fill('[role=dialog] input[aria-label="Base DN"]', 'dc=qa,dc=local')
      await page.click('[role=dialog] button[type=submit]:has-text("Salvar")')
      await ok(await existe(page, 'text=Configuração do diretório salva.'), 'diretório salvo')
      await page.fill('[role=dialog] input[aria-label="Usuário para testar"]', 'ana')
      await page.click('[role=dialog] button:has-text("Testar")')
      await ok(await existe(page, '[role=dialog] [role=alert]:has-text("Falha no diretório")', 12000), 'teste mostra que o diretório não responde')
      await print(page, 'ldap')

      // Diretório fora do ar: nome desconhecido recebe aviso claro; a conta local continua entrando.
      const outra = await ctx.browser().newContext({ viewport: { width: 1200, height: 800 } })
      await outra.addInitScript(DEFINIR_IDIOMA, 'pt')
      const login = await outra.newPage()
      await login.goto(WEB + '/')
      await login.fill('input[type=text]', 'ana.diretorio')
      await login.fill('input[type=password]', 'qualquer-senha')
      await login.click('button[type=submit]')
      await ok(await existe(login, 'text=/Não foi possível falar com o diretório/', 12000), 'aviso de diretório fora do ar no login')
      await outra.close()
    } finally {
      await api('PUT', '/config/alertas', { escalar_min: 0, escalar_emails: '' }, TOKEN).catch(() => {})
      await api('PUT', '/config/ldap', { ativo: false, servidor: '', base_dn: '' }, TOKEN).catch(() => {})
    }
  })

  if (process.env.QA_SNMPSIM) await cenario('Cabos pelo LLDP/CDP (agente simulado)', async ({ page, ok }) => {
    const [host, porta] = process.env.QA_SNMPSIM.split(':')
    const modelo = await api('POST', '/modelos', { nome: 'Lab LLDP', tipo: 'Switch Gerenciável', altura_u: 1, portas_rj45: 4, portas_sfp: 0, prefixo_porta: 'ge' }, TOKEN)
    const sw = { id: 'lldp', nome: 'Switch LLDP', ip: host, tipo: 'Switch Gerenciável', status: 'offline', posX: 0, posY: 0, width: 380, height: 28,
      rackId: 'r1', rackU: 8, alturaU: 1, monitorMode: 'snmpv3', modeloId: modelo.id,
      monitorConfig: { username: 'netcable', authProtocol: 'SHA', authPassword: 'authpass123', privProtocol: 'AES', privPassword: 'privpass123', port: Number(porta), context: 'public' } }
    try {
      await api('POST', `/projetos/${PID}/salvar`, { ...MAPA, equipamentos: [...MAPA.equipamentos, sw] }, TOKEN)
      await entrar(page); await abrirEditor(page)
      const antes = await page.locator('.react-flow__edge').count()
      await page.locator('button:has(svg.lucide-settings)').first().click()
      await page.click('button:has-text("Descobrir cabos (LLDP/CDP)")')
      await ok(await existe(page, '[role=dialog] h3:has-text("Cabos encontrados")', 30000), 'switch consultado')
      const linhas = page.locator('[role=dialog] section:has(h3:has-text("Cabos encontrados")) label')
      await ok(await linhas.count() === 3, `3 cabos sugeridos (firewall, NAS e AP) — ${await linhas.count()}`)
      await ok(await existe(page, '[role=dialog] >> text=printer-01'), 'vizinho fora do mapa listado')
      await print(page, 'cabos-lldp')
      await page.click('[role=dialog] button:has-text("Adicionar ao mapa (3)")')
      await ok(await existe(page, 'text=/3 cabo\\(s\\) e 0 equipamento\\(s\\) adicionados/'), 'cabos adicionados')
      await page.waitForTimeout(600)
      await ok(await page.locator('.react-flow__edge').count() === antes + 3, 'três cabos novos no mapa')
      await page.keyboard.press('Control+s')
      await page.waitForTimeout(1500)
      const dados = await api('GET', `/projetos/${PID}/dados`, null, TOKEN)
      const fw = dados.conexoes.find(c => [c.source, c.target].includes('lldp') && [c.source, c.target].includes('fw'))
      await ok(fw && fw.source_handle === 'p:1' && fw.target_handle === 'p:1', `cabo switch porta 1 ↔ firewall porta 1 (${fw?.source_handle} → ${fw?.target_handle})`)
    } finally {
      await restaurarMapa()
    }
  })
}

// ----------------------------------------------------------------------------- exploração livre
function aleatorio(semente) { let s = semente >>> 0; return () => ((s = (s * 1664525 + 1013904223) >>> 0) / 2 ** 32) }
const PROIBIDO = /^(Sair|Log out|Excluir|Delete|Revogar|Revoke|Gerar Novo Link|Generate New Link|Importar JSON|Import JSON)/i

async function explorar(idioma, semente) {
  const acoes = []
  const ctx = await navegador.newContext({ viewport: { width: 1400, height: 880 } })
  await ctx.addInitScript(DEFINIR_IDIOMA, idioma)
  vigiar(ctx, `Exploração (${idioma.toUpperCase()})`, acoes)
  const page = await ctx.newPage()
  page.on('dialog', d => (Math.random() < 0.5 ? d.accept() : d.dismiss()))
  await entrar(page)
  const rnd = aleatorio(semente)
  const rotas = [`${WEB}/projects`, `${WEB}/editor/${PID}`, `${WEB}/editor/${PID}`]
  for (let passo = 0; passo < PASSOS_EXPLORACAO; passo++) {
    try {
      if (passo % 12 === 0) {
        const rota = rotas[Math.floor(rnd() * rotas.length)]
        acoes.push(`abrir ${rota.replace(WEB, '')}`)
        await page.goto(rota); await page.waitForTimeout(600)
      }
      const candidatos = await page.$$eval('button, select, input[type=checkbox], [role=button]', (els) => els
        .map((el, i) => {
          const r = el.getBoundingClientRect()
          const visivel = r.width > 4 && r.height > 4 && r.bottom > 0 && r.top < innerHeight && getComputedStyle(el).visibility !== 'hidden' && !el.disabled
          const noModal = !!el.closest('[style*="z-index: 1000"], [style*="z-index: 1100"]')
          return visivel ? { i, tag: el.tagName, noModal, texto: (el.innerText || el.title || el.getAttribute('aria-label') || '').trim().slice(0, 40) } : null
        }).filter(Boolean))
      let opcoes = candidatos.filter(c => !PROIBIDO.test(c.texto))
      // Com um modal aberto, explora dentro dele na maior parte das vezes (formulários, testes, abas).
      const noModal = opcoes.filter(c => c.noModal)
      const modalAberto = noModal.length > 0
      if (modalAberto && rnd() < 0.8) opcoes = noModal
      if (!opcoes.length) continue
      const alvo = opcoes[Math.floor(rnd() * opcoes.length)]
      const el = (await page.$$('button, select, input[type=checkbox], [role=button]'))[alvo.i]
      if (!el) continue
      if (alvo.tag === 'SELECT') {
        const valores = await el.$$eval('option:not([disabled])', os => os.map(o => o.value))
        const v = valores[Math.floor(rnd() * valores.length)]
        acoes.push(`escolher "${v}" em lista`)
        await el.selectOption(v, { timeout: 2000 })
      } else {
        acoes.push(`clicar "${alvo.texto || alvo.tag}"`)
        await el.click({ timeout: 2000 })
      }
      await page.waitForTimeout(350)
      // Layout: modal com rolagem horizontal costuma ser texto/formulário estourando a largura.
      const estouro = await page.evaluate(() => [...document.querySelectorAll('div')].some(d => {
        const s = getComputedStyle(d)
        return (s.overflowX === 'auto' || s.overflowX === 'scroll') && d.scrollWidth > d.clientWidth + 2 && d.closest('[style*="z-index"]')
      }))
      if (estouro) R.achados.push({ tipo: 'layout', onde: `Exploração (${idioma.toUpperCase()})`, msg: 'Modal com rolagem horizontal (conteúdo mais largo que o modal)', passos: acoes.slice(-6), print: await print(page, `layout-${idioma}`) })
      if (rnd() < (modalAberto ? 0.12 : 0.25)) { await page.keyboard.press('Escape'); await page.locator('h2 + button').first().click({ timeout: 800 }).catch(() => {}) }
    } catch (e) {
      // Elemento sumiu / ficou coberto entre a listagem e o clique: comum e não é bug.
    }
  }
  await print(page, `exploracao-fim-${idioma}`)
  await ctx.close()
  log(`🔎 exploração ${idioma.toUpperCase()}: ${PASSOS_EXPLORACAO} passos`)
}

// ----------------------------------------------------------------------------- relatório
function escrever() {
  const fim = new Date()
  const totalChecks = R.cenarios.reduce((s, c) => s + c.checks.length, 0)
  const falhasCen = R.cenarios.filter(c => c.erro || c.checks.some(x => !x.ok))
  // Agrupa achados repetidos (o mesmo erro visto várias vezes conta uma vez).
  const grupos = new Map()
  for (const a of R.achados) {
    const chave = `${a.tipo}|${a.msg}`
    if (!grupos.has(chave)) grupos.set(chave, { ...a, vezes: 0, onde: new Set() })
    const g = grupos.get(chave); g.vezes++; g.onde.add(a.onde)
  }
  const achados = [...grupos.values()]
  const bugs = achados.filter(a => a.tipo === 'bug')
  const status = falhasCen.length || bugs.length ? '❌ PROBLEMAS ENCONTRADOS' : '✅ TUDO CERTO'

  const md = [
    `# Relatório de QA do NetCable — ${R.inicio.toLocaleString('pt-BR')}`,
    '',
    `**${status}** · ${R.cenarios.length} roteiros, ${totalChecks} verificações, ${PASSOS_EXPLORACAO * 2} passos de exploração · ${((fim - R.inicio) / 60000).toFixed(1)} min`,
    '',
    '## Roteiros',
    ...R.cenarios.map(c => {
      const f = c.checks.filter(x => !x.ok)
      const linha = `- ${c.erro || f.length ? '❌' : '✅'} **${c.nome}** (${c.checks.length - f.length}/${c.checks.length})`
      return [linha, ...f.map(x => `  - falhou: ${x.msg}`), ...(c.erro ? [`  - erro: ${c.erro}`] : [])].join('\n')
    }),
    '',
    '## Achados (erros de fundo, layout e tradução)',
    achados.length ? achados.map(a => `- [${a.tipo}] ${a.msg} — ${a.vezes}x em ${[...a.onde].join(', ')}${a.passos?.length ? `\n  - passos: ${a.passos.join(' → ')}` : ''}`).join('\n') : '- nenhum',
    '',
    `Relatório completo: relatorio.html · Logs do ambiente: ${TEMP}`,
  ].join('\n')
  fs.writeFileSync(path.join(PASTA, 'resumo.md'), md)

  const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' })[c])
  const html = `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><title>QA NetCable ${esc(carimbo)}</title><style>
  body{font-family:Segoe UI,Arial,sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:32px;max-width:1100px}
  h1{margin:0 0 6px} .st{font-size:20px;font-weight:bold;margin:10px 0 24px} .ok{color:#22c55e} .ruim{color:#ef4444} .aviso{color:#f59e0b}
  .card{background:#1e293b;border:1px solid #334155;border-radius:10px;padding:14px 18px;margin:10px 0}
  .card h3{margin:0 0 8px;font-size:16px} li{margin:3px 0} small{color:#94a3b8} img{max-width:100%;border:1px solid #334155;border-radius:6px;margin-top:8px}
  code{background:#0b1120;padding:1px 5px;border-radius:4px}
  </style></head><body>
  <h1>Relatório de QA do NetCable</h1><small>${esc(R.inicio.toLocaleString('pt-BR'))} · ${((fim - R.inicio) / 60000).toFixed(1)} min · ${esc(WEB)}</small>
  <div class="st ${falhasCen.length || bugs.length ? 'ruim' : 'ok'}">${status}</div>
  <h2>Roteiros (${R.cenarios.length})</h2>
  ${R.cenarios.map(c => `<div class="card"><h3 class="${c.erro || c.checks.some(x => !x.ok) ? 'ruim' : 'ok'}">${c.erro || c.checks.some(x => !x.ok) ? '❌' : '✅'} ${esc(c.nome)} <small>${(c.ms / 1000).toFixed(1)}s</small></h3>
    <ul>${c.checks.map(x => `<li class="${x.ok ? '' : 'ruim'}">${x.ok ? '✔' : '✘'} ${esc(x.msg)}</li>`).join('')}${c.erro ? `<li class="ruim">Erro: <code>${esc(c.erro)}</code></li>` : ''}</ul>
    ${c.prints.filter(Boolean).map(p => `<img src="${p}">`).join('')}</div>`).join('')}
  <h2>Achados da exploração e erros de fundo (${achados.length})</h2>
  ${achados.length ? achados.map(a => `<div class="card"><h3 class="${a.tipo === 'bug' ? 'ruim' : 'aviso'}">[${esc(a.tipo)}] ${esc(a.msg)}</h3>
    <small>${a.vezes}x · ${esc([...a.onde].join(', '))}</small>${a.passos?.length ? `<div><small>Passos: ${esc(a.passos.join(' → '))}</small></div>` : ''}${a.print ? `<img src="${a.print}">` : ''}</div>`).join('') : '<p class="ok">Nenhum.</p>'}
  </body></html>`
  fs.writeFileSync(path.join(PASTA, 'relatorio.html'), html)
  return { md, problemas: falhasCen.length + bugs.length }
}

// ----------------------------------------------------------------------------- execução
const canal = process.env.QA_BROWSER || (process.platform === 'win32' ? 'msedge' : undefined)
let navegador
try {
  log(`subindo ambiente isolado em ${TEMP} ...`)
  await subirAmbiente()
  navegador = await chromium.launch({ channel: canal, headless: !process.env.QA_VER })
  await cenario('Primeiro acesso (instalação nova)', async ({ page, ok }) => {
    await page.goto(WEB + '/')
    await ok(await existe(page, 'text=Primeiro acesso'), 'tela de primeiro acesso aparece numa instalação nova')
    await page.fill('input[aria-label="Usuário"]', ADMIN.usuario)
    await page.fill('input[aria-label="Senha (mín. 8)"]', ADMIN.senha)
    await page.fill('input[aria-label="Confirmar senha"]', 'diferente-123')
    await page.click('button:has-text("Criar administrador e entrar")')
    await ok(await existe(page, 'text=As senhas não conferem.'), 'avisa quando as senhas não conferem')
    await page.fill('input[aria-label="Confirmar senha"]', ADMIN.senha)
    await page.click('button:has-text("Criar administrador e entrar")')
    await ok(await page.waitForURL(/projects/, { timeout: 10000 }).then(() => true).catch(() => false), 'cria o admin e entra direto')
    const r = await fetch(`${API}/setup`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ username: 'intruso', senha: 'intruso-123' }) })
    await ok(r.status === 409, `não dá para criar outro "primeiro admin" depois (HTTP ${r.status})`)
  })
  await popularDados()
  log(`ambiente pronto: ${WEB}`)
  await roteiros()
  await restaurarMapa()
  await explorar('en', 20261117)
  await explorar('pt', 42)
} catch (e) {
  R.cenarios.push({ nome: 'Preparação do ambiente', checks: [], erro: e.message.split('\n')[0], prints: [], ms: 0 })
  log('❌ falha geral:', e.message)
} finally {
  await navegador?.close().catch(() => {})
  encerrarTudo()
}
const { md, problemas } = escrever()
console.log('\n' + md)
console.log(`\n[qa] relatório: ${path.join(PASTA, 'relatorio.html')}`)
process.exit(problemas ? 1 : 0)
