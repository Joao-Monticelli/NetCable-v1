"""Servidor SMTP falso usado pelo robô de QA: aceita qualquer e-mail e grava em JSONL.
Uso: python fake_smtp.py <porta> <arquivo_saida.jsonl>"""
import email
import json
import socketserver
import sys
from email import policy

SAIDA = sys.argv[2]


class Handler(socketserver.StreamRequestHandler):
    def enviar(self, linha):
        self.wfile.write((linha + "\r\n").encode())

    def handle(self):
        self.enviar("220 netcable-qa smtp")
        destinatarios = []
        while True:
            linha = self.rfile.readline()
            if not linha:
                return
            comando = linha.decode(errors="replace").strip()
            maiusculo = comando.upper()
            if maiusculo.startswith(("EHLO", "HELO")):
                self.enviar("250 netcable-qa")
            elif maiusculo.startswith("MAIL FROM"):
                destinatarios = []
                self.enviar("250 OK")
            elif maiusculo.startswith("RCPT TO"):
                destinatarios.append(comando.split(":", 1)[1].strip(" <>"))
                self.enviar("250 OK")
            elif maiusculo == "DATA":
                self.enviar("354 fim com .")
                partes = []
                while True:
                    bruto = self.rfile.readline()
                    if bruto in (b".\r\n", b".\n", b""):
                        break
                    partes.append(bruto[1:] if bruto.startswith(b"..") else bruto)
                msg = email.message_from_bytes(b"".join(partes), policy=policy.default)
                corpo = msg.get_body(("plain",))
                with open(SAIDA, "a", encoding="utf-8") as f:
                    f.write(json.dumps({"para": destinatarios, "assunto": msg["Subject"],
                                        "texto": corpo.get_content() if corpo else ""}, ensure_ascii=False) + "\n")
                self.enviar("250 OK")
            elif maiusculo == "QUIT":
                self.enviar("221 tchau")
                return
            else:
                self.enviar("250 OK")


socketserver.ThreadingTCPServer.allow_reuse_address = True
with socketserver.ThreadingTCPServer(("127.0.0.1", int(sys.argv[1])), Handler) as servidor:
    servidor.serve_forever()
