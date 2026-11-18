# Robô de QA do NetCable

Usa o NetCable como um usuário real e gera um relatório — **sem IA, sem gastar tokens**.

```bash
cd qa
npm install          # só na primeira vez
npm run qa           # completo (~3 min)
npm run qa:rapido    # rápido (~1,5 min, pula o roteiro lento do link público)
```

O relatório fica em `qa/relatorios/<data-hora>/relatorio.html` (com prints das falhas) e `resumo.md`.

## O que ele faz

1. Sobe uma instância **isolada**: backend com banco temporário (porta 8011), frontend (5184) e um SMTP falso (2526).
   Não mexe no seu banco nem no NetCable que você estiver usando.
2. **Roteiros**: login e idioma, adicionar equipamento (incluindo "Testar" e tempo de resposta), racks (montar, mover,
   salvar), modelos e cabos por porta, modo visualização e link público (TV), usuários e papéis, e-mail,
   histórico/latência/diagnóstico e aviso de alterações não salvas.
3. **Exploração livre** em inglês e português: clica aleatoriamente pelas telas e modais procurando
   exceções JavaScript, erros no console, respostas HTTP 5xx, textos sem tradução e modais quebrados.

O processo termina com código 1 se encontrar problemas (útil para CI).

## Variáveis opcionais

| Variável | Para quê |
|---|---|
| `QA_BROWSER` | Navegador: `msedge` (padrão no Windows), `chrome` ou vazio para o Chromium do Playwright (`npx playwright install chromium`) |
| `QA_VER=1` | Abre o navegador visível para acompanhar o robô |
| `QA_API_PORT`, `QA_WEB_PORT`, `QA_SMTP_PORT` | Trocar as portas da instância de teste |

No Claude Code, o comando `/qa-diario` roda o robô e resume o relatório.
