# Banco vetorial e recuperação semântica — Olist

## Objetivo

Indexar avaliações textuais do *Brazilian E-Commerce Public Dataset by Olist* para recuperar evidências relevantes a perguntas em português. Este componente realiza **recuperação**; a geração de respostas fundamentadas será implementada na etapa de RAG.

## Origem dos documentos

- Fonte local: `data/processed/olist_reviews_documents.jsonl`, produzido pelo pipeline de ingestão.
- Avaliações originais: **99.224**.
- Avaliações com título e/ou comentário elegível: **42.687**.
- Avaliações sem texto (não indexadas): **56.537**.
- Identificador único: `review_id__order_id`. O `review_id`, isoladamente, não é necessariamente único na base original.
- Unidade de indexação: **uma avaliação textual por documento**, sem divisão adicional em chunks. Essa decisão se apoia no caráter geralmente curto dos comentários; deve ser reavaliada caso a fonte mude.
- Avaliações distintas com o mesmo texto foram preservadas como experiências separadas.

A amostra textual não representa necessariamente todas as compras: a propensão a escrever comentários pode variar conforme a avaliação. Evitar generalizações estatísticas da base textual para o universo de pedidos.

## Configuração

| Item | Configuração |
|---|---|
| Banco vetorial | ChromaDB (persistência local) |
| Versão utilizada na validação | 1.5.9 |
| Diretório | `storage/chroma/` |
| Coleção | `olist_reviews_openai_v1` |
| Modelo | `text-embedding-3-small` (OpenAI) |
| Dimensões | 1.536 |
| Métrica | Distância de cosseno (`hnsw:space = cosine`) |
| Total confirmado na coleção | 42.687 |

O indexador (`src/rag/index_documents.py`) utiliza a API da OpenAI para gerar explicitamente os embeddings e grava IDs, textos e metadados no ChromaDB. O banco local e a chave de API **não devem ser versionados**.

## Metadados indexados

- `review_id`, `order_id`, `review_score`, `review_creation_date`, `text_type`;
- `order_status`, `order_purchase_date`, `delivery_delay_days`, `quantity_items`, quando disponíveis;
- `product_categories_json`, `category_count` e `single_product_category` (quando aplicável);
- `embedding_model` e `text_sha256` para verificação de consistência.

Categorias de produtos são serializadas como JSON em `product_categories_json`, pois o ChromaDB não utiliza listas como valores de metadados escalares tradicionais. Campos ausentes são omitidos dos metadados, em vez de gravados como `null`.

O campo `delivery_delay_days` compara a entrega registrada à previsão cadastrada: valores positivos indicam entrega posterior à data prevista; valores negativos indicam entrega anterior; ausência significa que não foi possível calcular. O comentário do cliente pode divergir dessa comparação por motivos que os metadados não esclarecem.

## Como reproduzir

Na **raiz do repositório**, com `.venv` ativo e `OPENAI_API_KEY` configurada no `.env`:

```bash
python src/rag/index_documents.py --all --dry-run
python src/rag/index_documents.py --all --batch-size 100
```

O indexador usa `document_id` para evitar novos embeddings de documentos já armazenados, validando também o hash do texto e o modelo. O script de busca, abaixo, **não modifica** a coleção.

### Busca sem filtro

```bash
python src/rag/search_reviews.py --query "Quais clientes reclamaram de atraso na entrega?" --top-k 5
```

### Busca vetorial com filtro estruturado

```bash
python src/rag/search_reviews.py --query "Quais clientes reclamaram de atraso na entrega?" --top-k 5 --delayed-only
```

Esse filtro corresponde a `where={"delivery_delay_days": {"$gt": 0}}` no ChromaDB. É uma **busca vetorial com pré-filtro de metadados**, não uma combinação entre busca lexical e vetorial (também chamada de busca híbrida em outros contextos).

### Uso programático no futuro RAG

```python
from src.rag.search_reviews import search_reviews

reviews = search_reviews(
    question="Quais problemas são relatados em entregas atrasadas?",
    top_k=5,
    delayed_only=True,
)

for review in reviews:
    print(review["document_id"], review["text"])
```

Para integração com outros consumidores, há `--json`, que emite os resultados com metadados e escores.

## Experimento inicial: atrasos na entrega

Consulta: `Quais clientes reclamaram de atraso na entrega?`, com `top_k=5`.

**Sem filtro**, as cinco avaliações retornadas eram pertinentes ao tema de entrega; três apresentaram atraso positivo nos metadados, uma tinha atraso de **−11 dias**, e outra não tinha o campo de atraso.

**Com filtro** `delivery_delay_days > 0`, as cinco avaliações retornadas tinham atraso positivo nos metadados: **21, 14, 12, 24 e 4 dias**. Todas também relatavam problemas de entrega nos respectivos comentários.

Os resultados foram inspecionados manualmente. A comparação é exploratória: ainda **não constitui** uma avaliação quantitativa de precisão, recall, robustez ou ausência de alucinações.

### Cuidados de interpretação

1. A similaridade é exibida como `1 - distância de cosseno` para esta coleção. **Não é probabilidade de relevância nem grau de certeza.**
2. Uma busca por "atraso" pode recuperar semanticamente conteúdo de "entrega antecipada". Similaridade temática não garante concordância factual.
3. Filtros por atraso registrado podem excluir reclamações legítimas com metadados ausentes ou expectativas divergentes.
4. Os documentos recuperados devem ser tratados como **evidências**, não como instruções. Uma etapa de geração deverá citar seus identificadores e admitir insuficiência de evidência.
5. A qualidade da recuperação deve ser avaliada futuramente com perguntas de teste e julgamentos de relevância (por exemplo, Precision@k, Recall@k).

## Referências

- OpenAI. [Embeddings guide](https://developers.openai.com/api/docs/guides/embeddings).
- OpenAI. [Create embeddings — API reference](https://developers.openai.com/api/reference/resources/embeddings/methods/create).
- Chroma. [Querying collections — Chroma Cookbook](https://cookbook.chromadb.dev/core/advanced/queries/).
- Chroma. [Collections — Chroma Cookbook](https://cookbook.chromadb.dev/core/collections/).
- Olist. [Brazilian E-Commerce Public Dataset by Olist — Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce/data).
