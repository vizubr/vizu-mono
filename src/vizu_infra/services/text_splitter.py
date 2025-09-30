from langchain.text_splitter import RecursiveCharacterTextSplitter
def dividir_texto_em_chunks(texto_bruto: str) -> list[str]:
    """
    Divide um texto longo em chunks menores usando uma estratégia recursiva.

    Esta estratégia tenta manter parágrafos, frases e palavras juntos o
    máximo possível.

    Args:
        texto_bruto: A string de texto a ser dividida.

    Returns:
        Uma lista de strings, onde cada item é um chunk de texto.
    """
    if not texto_bruto:
        print("Aviso: Texto de entrada está vazio. Nenhum chunk gerado.")
        return []

    # Configuração do divisor de texto
    # chunk_size: O tamanho máximo de cada chunk (em caracteres).
    # chunk_overlap: O número de caracteres que se sobrepõem entre chunks
    #                consecutivos. Isso ajuda a manter o contexto.
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
        length_function=len,
    )

    chunks = text_splitter.split_text(texto_bruto)
    print(f"Texto dividido em {len(chunks)} chunks.")
    return chunks

# Exemplo de como usar (para testes)
if __name__ == '__main__':
    texto_exemplo = """
    O Atendente Virtual da Vizu é uma solução de IA de ponta.
    Ele foi projetado para ser modular, escalável e de alto desempenho.
    A aplicação principal será executada em uma Máquina Virtual (VM) e se comunicará com um conjunto de bancos de dados especializados.
    A identificação do Cliente (PME) é realizada através da linha telefônica dedicada.
    Este número de telefone serve como a chave identificadora principal para o acesso a todos os dados subsequentes.
    Os componentes de armazenamento incluem um Banco de Dados SQL, um Banco Vetorial (Qdrant) e um Banco de Cache em Memória (Redis).
    Esta arquitetura garante robustez e eficiência para todos os nossos clientes.
    """ * 5 # Multiplicando para simular um texto maior

    chunks_gerados = dividir_texto_em_chunks(texto_exemplo)

    print("\\n--- Chunks Gerados ---")
    for i, chunk in enumerate(chunks_gerados):
        print(f"--- Chunk {i+1} (Tamanho: {len(chunk)}) ---")
        print(chunk)
        print()