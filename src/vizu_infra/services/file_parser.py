from pypdf import PdfReader
import io
import requests # Para baixar o arquivo de uma URL (ex: S3)

def extrair_texto_de_pdf(uri_arquivo: str) -> str:
    """
    Baixa um arquivo PDF de uma URI e extrai todo o texto contido nele.

    Args:
        uri_arquivo: A URL pública do arquivo PDF.

    Returns:
        Uma única string com o texto completo do PDF.
    """
    try:
        # Em um cenário real, teríamos uma lógica para baixar do S3.
        # Por enquanto, vamos simular o download via uma requisição HTTP.
        response = requests.get(uri_arquivo)
        response.raise_for_status() # Lança um erro se o download falhar

        # Lê o conteúdo do PDF em memória
        arquivo_pdf_em_memoria = io.BytesIO(response.content)

        leitor_pdf = PdfReader(arquivo_pdf_em_memoria)
        texto_completo = []

        for pagina in leitor_pdf.pages:
            texto_completo.append(pagina.extract_text())

        print(f"Texto extraído com sucesso de {uri_arquivo}")
        return "\\n".join(texto_completo)

    except Exception as e:
        print(f"Erro ao processar o PDF da URI {uri_arquivo}: {e}")
        # Em um cenário real, propagaríamos o erro para o worker lidar com ele.
        raise

# Exemplo de como usar (para testes)
if __name__ == '__main__':
    # Use um link para um PDF de exemplo online
    url_exemplo = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
    texto_extraido = extrair_texto_de_pdf(url_exemplo)
    print("--- Texto Extraído ---")
    print(texto_extraido)