import os
import requests
import subprocess
import sys

# URL do seu repositório raw no GitHub
URL_CODE = "https://raw.githubusercontent.com/SEU_USUARIO/SEU_REPO/main/sistema_final.py"
ARQUIVO_LOCAL = "sistema_final.py"

def verificar_atualizacao():
    try:
        # Baixa a versão mais recente
        resposta = requests.get(URL_CODE)
        if resposta.status_code == 200:
            novo_codigo = resposta.text
            # Verifica se o código mudou comparando com o local
            if os.path.exists(ARQUIVO_LOCAL):
                with open(ARQUIVO_LOCAL, "r", encoding="utf-8") as f:
                    codigo_atual = f.read()
                if novo_codigo == codigo_atual:
                    return # Não precisa atualizar
            
            # Atualiza o arquivo
            with open(ARQUIVO_LOCAL, "w", encoding="utf-8") as f:
                f.write(novo_codigo)
    except:
        pass # Se não houver internet, abre o que tiver localmente

if __name__ == "__main__":
    verificar_atualizacao()
    # Executa o sistema
    subprocess.Popen([sys.executable, ARQUIVO_LOCAL])