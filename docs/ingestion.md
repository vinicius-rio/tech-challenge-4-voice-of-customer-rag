
# Pipeline de Ingestão — Olist Reviews

## Objetivo

Construir uma base de conhecimento estruturada a partir das avaliações textuais da Olist, preservando a rastreabilidade e enriquecendo os documentos com metadados de negócio.

## Fontes de dados

- `olist_order_reviews_dataset.csv`
- `olist_orders_dataset.csv`
- `olist_order_items_dataset.csv`
- `olist_products_dataset.csv`

## Regras de processamento

1. Selecionar avaliações com título e/ou mensagem.
2. Excluir avaliações sem conteúdo textual.
3. Normalizar espaços, preservando acentuação, pontuação e capitalização.
4. Utilizar `review_id` e `order_id` para identificar cada documento.
5. Preservar avaliações distintas com textos repetidos.
6. Agregar informações de itens e categorias por pedido.
7. Representar metadados indisponíveis como `null`.
8. Exportar os documentos em JSONL.

## Resultados

| Indicador | Quantidade |
|---|---:|
| Avaliações originais | 99.224 |
| Documentos gerados | 42.687 |
| Avaliações sem texto | 56.537 |
| Documentos com título e mensagem | 9.829 |
| Documentos somente com mensagem | 31.121 |
| Documentos somente com título | 1.737 |

## Cobertura dos metadados

| Campo | Disponíveis |
|---|---:|
| `order_status` | 42.687 |
| `order_purchase_date` | 42.687 |
| `delivery_delay_days` | 40.785 |
| `product_categories` | 41.554 |
| `quantity_items` | 42.157 |

## Execução

Na raiz do repositório, com o ambiente Python configurado:

```bash
python src/ingestion/build_documents.py
python src/ingestion/validate_enrichment.py
```

## Artefatos gerados

- `data/processed/olist_reviews_documents.jsonl`
- `data/processed/ingestion_report.json`

Os artefatos processados são gerados localmente e não precisam ser versionados no GitHub.

## Validação

A execução do validador confirmou:

- 42.687 documentos válidos e identificadores únicos.
- Preservação dos textos originais.
- Exclusão de 56.537 avaliações sem texto.
- Consistência do relatório de ingestão.
- Integridade dos metadados verificados.

## Limitações

- Avaliações sem texto não integram a base vetorial.
- Títulos isolados podem conter pouca informação semântica.
- Metadados ausentes não devem ser interpretados como valores negativos ou zero.
- Categorias descrevem os produtos associados ao pedido e podem incluir múltiplas categorias.
- A recuperação semântica isolada não fornece estimativas representativas de frequência.
