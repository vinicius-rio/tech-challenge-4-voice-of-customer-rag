# Interface FIAP — Voice of Customer Intelligence

Uma interface conversacional **Streamlit** conectada ao pipeline RAG existente do projeto. O visual reproduz a identidade FIAP da apresentação da Fase 3 e a estrutura do simulador de celular.

## O que faz

- Chat em formato de celular com perguntas livres e sugestões clicáveis.
- Consulta real a `src.rag.answer_reviews.answer_question` — nenhuma resposta é simulada.
- Filtro opcional para pedidos com atraso registrado e Top-K configurável.
- Painel lateral para comentários, documento, nota, atraso, status e distância/similaridade de cosseno.
- Painel de execução com latência ponta a ponta, modelo e tokens de **geração de texto** (não incluem embedding).
- Histórico em memória por sessão da aplicação.

**Fora de escopo desta versão:** Precision@k, Recall@k e Faithfulness. Nenhum valor dessas métricas é inventado.

## Instalação (Git Bash / Windows)

1. Extraia os arquivos deste pacote na **raiz do repositório**, preservando os subdiretórios.
2. Com `.venv` ativado, instale a interface:

   ```bash
   python -m pip install -r requirements-ui.txt
   ```

   As bibliotecas existentes (`chromadb`, `openai`, `python-dotenv` etc.) devem estar instaladas como na execução anterior do RAG.

3. Atualize o retorno das fontes — **preserva todas as regras do seu SYSTEM_PROMPT**:

   ```bash
   python scripts/extend_rag_sources.py
   ```

4. Execute os testes existentes:

   ```bash
   python -m unittest discover -s tests -p "test_rag_generation.py" -v
   ```

5. Inicie a interface:

   ```bash
   python -m streamlit run app.py
   ```

## Requisitos dos dados

- Arquivo `.env` na raiz com `OPENAI_API_KEY` válido.
- Banco vetorial local `storage/chroma`, com a coleção `olist_reviews_openai_v1` indexada.
- A aplicação não recria embeddings dos 42.687 documentos; cria apenas o embedding da **pergunta**, como o RAG original.

## Notas de observabilidade

- `cosine_distance` provém do `collection.query()` do ChromaDB.
- `cosine_similarity = 1 - cosine_distance`, não é uma probabilidade calibrada de relevância.
- A latência inclui todo o tempo de chamada de `answer_question()` (embedding, recuperação, geração).
- Os tokens de entrada/saída reportados pelo backend correspondem apenas à etapa de **geração**.
- O modelo realiza nova consulta a cada pergunta; o chat guarda histórico visual, mas o backend **não** adiciona as mensagens anteriores ao prompt. Portanto, perguntas dependentes de contexto anterior não são interpretadas automaticamente.
- Os textos dos consumidores são escapados antes de serem renderizados em HTML para evitar injeção na interface.

## Limitação de implantação

A coleção ChromaDB é local e não está versionada no Git. Um deploy em Streamlit Community Cloud **não funcionará** sem uma estratégia separada para disponibilizar o índice e proteger a chave OpenAI. Execute localmente nesta etapa.

## Teste adicional de contrato

Depois de aplicar a extensão, rode também:

```bash
python -m unittest discover -s tests -p "test_rag_ui_contract.py" -v
```

Esse teste verifica que a resposta do backend repassa distância, similaridade e metadados sem chamadas externas.
