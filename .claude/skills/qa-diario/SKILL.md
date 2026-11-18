---
name: qa-diario
description: Roda o robô de QA do NetCable (qa/qa.mjs) — usa o sistema como um usuário real numa instância isolada — e resume o relatório gastando poucos tokens. Use quando o usuário pedir "/qa-diario", "roda o QA", "relatório de QA" ou quiser checar bugs no fim do dia.
---

# QA diário do NetCable

O robô não usa IA: quem gasta tokens aqui é só a leitura do resumo. Mantenha assim.

1. Se `qa/node_modules` não existir, rode `npm install` dentro de `qa/`.
2. Rode o robô a partir de `qa/` (leva ~3 min; o modo `--rapido` leva ~1,5 min e pula o roteiro lento do link público):
   `node qa.mjs` — use `--rapido` se o usuário pedir algo rápido.
   Ele sobe backend/frontend/SMTP falsos em portas próprias (8011/5184/2526) com banco temporário:
   não mexe no banco nem nos servidores de desenvolvimento do usuário.
3. Leia **apenas** o `resumo.md` da pasta mais recente em `qa/relatorios/` (a saída do comando já termina com ele).
   Não abra o `relatorio.html`, os prints nem os logs, a não ser para investigar uma falha específica.
4. Responda em português, curto:
   - Tudo certo: uma linha com o placar (roteiros, verificações, passos de exploração) e o caminho do `relatorio.html`.
   - Com problemas: liste cada falha/achado em uma linha e pergunte se o usuário quer que você investigue e corrija.
     Ao investigar, abra só o print/log daquela falha.
5. Achados do tipo `traducao` são textos sem tradução em `frontend/src/i18n/en.js`; `layout` é modal com rolagem
   horizontal; `bug` é exceção JavaScript, erro no console ou HTTP 5xx.
