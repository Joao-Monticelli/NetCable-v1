// Internacionalização simples do NetCable.
// - Os textos no código ficam em português e funcionam como chave.
// - Inglês é o idioma padrão: o dicionário en.js traduz cada chave.
// - t('Olá {nome}', { nome }) faz interpolação.
// - A escolha fica no localStorage (por navegador) e no perfil do usuário (para e-mails).
import { createContext, useContext, useState, useCallback, useMemo } from 'react'
import en from './en'

const CHAVE = 'netcable_idioma'
export const IDIOMAS = [
  { codigo: 'en', rotulo: 'English', bandeira: '🇺🇸' },
  { codigo: 'pt', rotulo: 'Português', bandeira: '🇧🇷' },
]
const valido = (i) => IDIOMAS.some(x => x.codigo === i)

let idiomaAtual = (() => {
  try { const salvo = localStorage.getItem(CHAVE); return valido(salvo) ? salvo : 'en' } catch { return 'en' }
})()
if (typeof document !== 'undefined') document.documentElement.lang = idiomaAtual === 'pt' ? 'pt-BR' : 'en'

export const getIdioma = () => idiomaAtual
export const localeAtual = () => (idiomaAtual === 'pt' ? 'pt-BR' : 'en-US')

const faltando = new Set()
// Função pura: pode ser usada fora de componentes (ex.: services/api.js, rackUtils).
export function t(texto, vars) {
  let s = texto
  if (idiomaAtual === 'en') {
    if (en[texto] !== undefined) s = en[texto]
    else if (import.meta.env?.DEV && !faltando.has(texto)) { faltando.add(texto); console.warn(`[i18n] tradução faltando: "${texto}"`) }
  }
  if (vars) s = s.replace(/\{(\w+)\}/g, (m, k) => (vars[k] !== undefined && vars[k] !== null ? vars[k] : m))
  return s
}

const I18nContext = createContext({ idioma: idiomaAtual, setIdioma: () => {}, t })

export function I18nProvider({ children }) {
  const [idioma, setIdiomaState] = useState(idiomaAtual)
  const setIdioma = useCallback((novo) => {
    if (!valido(novo)) return
    idiomaAtual = novo
    try { localStorage.setItem(CHAVE, novo) } catch { /* modo privado */ }
    document.documentElement.lang = novo === 'pt' ? 'pt-BR' : 'en'
    setIdiomaState(novo)
  }, [])
  // O objeto muda quando o idioma muda: todos os componentes que usam useI18n re-renderizam.
  const valor = useMemo(() => ({ idioma, setIdioma, t }), [idioma, setIdioma])
  return <I18nContext.Provider value={valor}>{children}</I18nContext.Provider>
}

export const useI18n = () => useContext(I18nContext)

// Seletor de idioma reutilizável (login, menus, página pública).
export function SeletorIdioma({ onChange, compacto = false, style }) {
  const { idioma, setIdioma } = useI18n()
  return (
    <div role="group" aria-label="Language / Idioma" style={{ display: 'inline-flex', border: '1px solid #334155', borderRadius: '6px', overflow: 'hidden', ...style }}>
      {IDIOMAS.map(i => (
        <button key={i.codigo} type="button" title={i.rotulo} aria-pressed={idioma === i.codigo}
          onClick={() => { if (idioma !== i.codigo) { setIdioma(i.codigo); onChange?.(i.codigo) } }}
          style={{ padding: compacto ? '4px 7px' : '6px 10px', border: 0, cursor: 'pointer', fontSize: '12px', fontWeight: 'bold',
            background: idioma === i.codigo ? '#3b82f6' : 'transparent', color: idioma === i.codigo ? 'white' : '#94a3b8' }}>
          {i.codigo.toUpperCase()}
        </button>
      ))}
    </div>
  )
}
