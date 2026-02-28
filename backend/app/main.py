from fastapi import FastAPI

# Cria a nossa aplicação
app = FastAPI(title="API de Automação")

# Cria a rota principal só para testarmos se está viva
@app.get("/")
def home():
    return {
        "status": "OK", 
        "mensagem": "Motor de automação rodando 100%!",
        "banco_de_dados": "Aguardando conexões..."
    }