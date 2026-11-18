# Voice of Customer Intelligence com RAG

**FIAP Pós-Tech — AI Scientist | Tech Challenge — Fase 4**

Aplicação conversacional para investigar a experiência de compra dos consumidores do e-commerce brasileiro. A solução utiliza **Retrieval-Augmented Generation (RAG)** para responder perguntas em português com base em avaliações reais da Olist, apresentando as fontes recuperadas e permitindo inspecionar a execução do pipeline.

## Visão geral

A análise manual de milhares de comentários dificulta identificar reclamações, elogios e evidências específicas sobre a jornada de compra. Este projeto transforma avaliações textuais não estruturadas em uma base consultável por linguagem natural.

A interface **Streamlit**, com identidade visual FIAP, oferece:

- **Chat conversacional** em um simulador de smartphone, com perguntas sugeridas e histórico visual da sessão.
- **Exploração inteligente** com configuração de `top_k` e filtro de pedidos entregues após a data prevista.
- **RAG Inspector** com textos originais, IDs, notas, informações do pedido, categorias, distância e similaridade de cosseno.
- **Observabilidade** de latência ponta a ponta e tokens informados pelo modelo gerador.
- **Respostas referenciadas**, com orientação para admitir insuficiência ou conflito entre evidências.

> **Escopo das conclusões:** as respostas são baseadas nos documentos recuperados para uma pergunta, **não em uma análise estatística de toda a base**. A similaridade de cosseno não equivale à probabilidade de uma afirmação estar correta.

## Demonstração em vídeo

**Veja o Voice of Customer Intelligence em funcionamento.** O vídeo de apresentação mostrará o chatbot com identidade visual FIAP, as perguntas em linguagem natural, a recuperação semântica e o **RAG Inspector**, incluindo as avaliações utilizadas como evidências e as métricas reais de execução.

> **Vídeo de demonstração (até 7 minutos):** link a ser adicionado após a publicação.

<!-- Após publicar o vídeo, substitua o aviso acima por:
[▶ Assistir à demonstração da solução](URL_DO_VIDEO)

Opcional: para usar uma miniatura clicável no GitHub, utilize:
[![Demonstração do Voice of Customer Intelligence](URL_DA_IMAGEM)](URL_DO_VIDEO)
-->

## Dataset

**Fonte:** [Brazilian E-Commerce Public Dataset by Olist — Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce/data).

| Indicador | Quantidade |
|---|---:|
| Registros de avaliações no CSV original | 99.224 |
| Avaliações com título e/ou comentário textual | 42.687 |
| Avaliações sem texto, excluídas da indexação | 56.537 |
| Documentos textuais indexados na execução validada | 42.687 |

Cada avaliação textual é preservada como um documento, sem *chunking* adicional, identificado por `review_id__order_id`. Isso evita presumir que `review_id` seja único isoladamente. Avaliações distintas com o mesmo comentário não são eliminadas.

O pipeline enriquece os textos com metadados de pedidos, notas, compra, entrega e categorias de produtos, quando disponíveis. O campo `delivery_delay_days` indica a diferença entre entrega registrada e previsão: **positivo** para entrega depois do prazo; **negativo** para entrega antes do prazo. O relato escrito pelo cliente pode divergir dos metadados estruturados.

## Arquitetura

```text
                      INDEXAÇÃO (OFFLINE)
Olist CSVs (avaliações, pedidos, itens, produtos)
             │
             ▼
Limpeza + enriquecimento + validação
             │
             ▼
JSONL: 1 documento por avaliação textual
             │
             ▼
OpenAI text-embedding-3-small (1.536 dimensões)
             │
             ▼
ChromaDB persistente ─ coleção olist_reviews_openai_v1

                      CONSULTA (ONLINE)
Pergunta do usuário no chatbot FIAP
             │
             ▼
Embedding da pergunta (text-embedding-3-small)
             │
             ▼
Busca semântica no ChromaDB (distância de cosseno)
             │   [top-k; filtro de atraso opcional]
             ▼
Contexto com comentários, metadados e referências [1], [2] ...
             │
             ▼
OpenAI gpt-4.1-mini (geração fundamentada)
             │
             ├──► Resposta no celular com referências
             └──► RAG Inspector: evidências e telemetria
```

### Decisões técnicas

- **Granularidade:** uma avaliação textual por documento, pela natureza curta dos relatos e para manter rastreabilidade individual.
- **Embeddings:** `text-embedding-3-small`, com 1.536 dimensões.
- **Armazenamento:** ChromaDB local persistente em `storage/chroma/`, coleção `olist_reviews_openai_v1`, com métrica de cosseno.
- **Recuperação:** `top_k` configurável e filtro estruturado opcional `delivery_delay_days > 0`. Trata-se de recuperação vetorial com filtro de metadados; não de busca híbrida lexical/vetorial.
- **Geração:** `gpt-4.1-mini`, com instruções de fundamentação, citações, não generalização e tratamento explícito de divergências.
- **Segurança de dados:** comentários são tratados como conteúdo não confiável; a aplicação escapa textos na renderização e não deve expor chaves ou dados pessoais.

## Tecnologias

| Componente | Implementação |
|---|---|
| Linguagem | Python 3.12 (ambiente utilizado no desenvolvimento) |
| Processamento dos CSVs | Biblioteca padrão do Python (`csv`, `json`, etc.) |
| Embeddings e geração | API OpenAI (`text-embedding-3-small` e `gpt-4.1-mini`) |
| Base vetorial | ChromaDB 1.5.9 |
| Interface web | Streamlit 1.67.0 + CSS personalizado |
| Configuração | `python-dotenv` |
| Testes | `unittest` |
| Versionamento | Git e GitHub |

O código do pipeline utiliza diretamente os SDKs OpenAI e ChromaDB; **LangChain não é uma dependência deste projeto**.

## Estrutura do repositório

```text
.
├── app.py                          # Interface conversacional Streamlit
├── ui_inspector.py                 # Formatação de fontes e evidências
├── assets/fiap.css                 # Identidade visual e layout
├── .streamlit/config.toml          # Tema público da interface
├── .env.example                    # Modelo de configuração, sem chave real
├── requirements.txt               # Dependências do projeto
├── requirements-ui.txt            # Alias de instalação da interface
├── data/
│   ├── raw/                        # CSVs originais (não versionados)
│   └── processed/                  # JSONL e relatórios (não versionados)
├── storage/chroma/                 # Índice vetorial local (não versionado)
├── notebooks/01_eda_olist_reviews.ipynb
├── src/
│   ├── ingestion/
│   │   ├── build_documents.py
│   │   └── validate_enrichment.py
│   ├── rag/
│   │   ├── index_documents.py
│   │   ├── search_reviews.py
│   │   └── answer_reviews.py
│   └── evaluation/
│       ├── evaluate_rag.py
│       └── rag_evaluation_cases.json
├── docs/
│   ├── ingestion.md
│   ├── vector_store.md
│   └── rag_evaluation.md
└── tests/                         # Testes automatizados
```

O repositório contém arquivos `.gitkeep` para preservar diretórios vazios. O banco ChromaDB, os dados originais/processados e o `.env` **não são distribuídos pelo GitHub**.

## Instalação e reprodução

Os exemplos abaixo utilizam **Git Bash no Windows**. É necessário ter Python instalado, acesso à internet e uma chave válida da API OpenAI com saldo/permissão para embeddings e geração.

### 1. Clonar e criar um ambiente virtual

```bash
git clone https://github.com/vinicius-rio/tech-challenge-4-voice-of-customer-rag.git
cd tech-challenge-4-voice-of-customer-rag
python -m venv .venv
source .venv/Scripts/activate
python -m pip install -r requirements.txt
```

Para ambientes Linux/macOS, a ativação costuma ser `source .venv/bin/activate`.

### 2. Configurar a OpenAI

```bash
cp .env.example .env
```

Edite **somente o arquivo `.env` local** e defina `OPENAI_API_KEY` com sua chave real. Nunca inclua essa chave em commits, prints ou relatórios.

### 3. Disponibilizar os CSVs da Olist

Baixe o dataset original no Kaggle e extraia estes **quatro arquivos** diretamente em `data/raw/`:

```text
data/raw/olist_order_reviews_dataset.csv
data/raw/olist_orders_dataset.csv
data/raw/olist_order_items_dataset.csv
data/raw/olist_products_dataset.csv
```

### 4. Construir e validar os documentos

```bash
python src/ingestion/build_documents.py
python src/ingestion/validate_enrichment.py
```

Saída principal: `data/processed/olist_reviews_documents.jsonl`. O processo também produz relatórios locais de auditoria.

### 5. Gerar o índice vetorial

```bash
# Verificação sem chamadas à API nem alteração do ChromaDB
python src/rag/index_documents.py --all --dry-run

# Indexação efetiva da base completa (faz chamadas pagas à OpenAI)
python src/rag/index_documents.py --all --batch-size 100
```

**Atenção:** executar `index_documents.py` sem `--all` indexa apenas os primeiros **10 documentos** por padrão. A indexação de toda a base consome API e pode levar algum tempo. A implementação verifica IDs, modelo e integridade para evitar processamento desnecessário de documentos já indexados.

### 6. Executar buscas e gerar respostas

```bash
# Recuperação semântica, sem geração de resposta
python src/rag/search_reviews.py --query "Reclamações sobre atraso na entrega" --top-k 5

# Busca apenas entre pedidos com atraso registrado
python src/rag/search_reviews.py --query "Reclamações sobre atraso" --top-k 5 --delayed-only

# RAG completo: recuperação + resposta com referências
python -m src.rag.answer_reviews --query "O que os clientes relatam sobre produtos quebrados?" --top-k 5
```

### 7. Iniciar a interface FIAP

```bash
python -m streamlit run app.py
```

Abra `http://localhost:8501` no navegador. O RAG Inspector mostra informações associadas à consulta e aos documentos recuperados.

**Nota:** a interface registra o histórico **visual** da conversa, mas, nesta versão, não inclui automaticamente turnos anteriores no contexto de novas perguntas. Consultas dependentes de contexto anterior podem exigir reformulação.

## Avaliação e testes

### Testes automatizados

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

Na validação da interface foram aprovados **19 testes**, cobrindo geração, referências, integração entre backend e UI, apresentação de metadados e regressões de layout. Esses testes não substituem uma avaliação semântica completa das respostas.

### Cenários de avaliação RAG

```bash
# Validar a estrutura dos seis cenários, sem consumir API
python -m src.evaluation.evaluate_rag --dry-run

# Execução real: gera respostas e grava relatório local (consome API)
python -m src.evaluation.evaluate_rag
```

Resultados históricos da avaliação inicial:

| Indicador | Resultado |
|---|---:|
| Cenários avaliados | 6 |
| Aprovação das verificações automáticas heurísticas | 6/6 |
| Respostas adequadas na revisão humana inicial | 3/6 |
| Respostas com ressalvas na revisão humana inicial | 3/6 |
| Teste controlado posterior de evidências conflitantes | Aprovado |

As heurísticas verificam aspectos estruturais, presença de citações e certos comportamentos de abstenção; **não comprovam fidelidade factual**. O teste controlado posterior demonstrou que o gerador identificou uma contradição entre um comentário que afirmava entrega dentro do prazo e o registro estruturado de atraso de 112 dias, sem inventar uma causa.

**Não foram calculadas:** Precision@k, Recall@k e Faithfulness quantitativa. Essas métricas exigem um protocolo adicional de avaliação, como documentos relevantes rotulados e julgamento fundamentado das afirmações geradas. Os seis cenários originais não foram integralmente reavaliados após todas as alterações do prompt.

Mais detalhes: [`docs/rag_evaluation.md`](docs/rag_evaluation.md).

## Limitações conhecidas

- O índice ChromaDB é local e não é disponibilizado no GitHub. A reprodução requer preparação e indexação da base; um deploy remoto exige infraestrutura adicional.
- A API OpenAI é um serviço externo e gera custos para embeddings e respostas.
- Resultados top-k não representam frequências ou proporções de toda a população de consumidores.
- Distância/similaridade de cosseno expressa proximidade vetorial, não relevância comprovada, confiança calibrada ou faithfulness.
- Os metadados de entrega podem refletir a situação final do pedido, diferente do momento em que a avaliação foi escrita.
- A avaliação sistemática ainda é limitada: seis cenários e checagens automáticas sobretudo heurísticas.
- O histórico do chat não é passado automaticamente ao modelo como memória conversacional.

## Documentação complementar

- [Ingestão e enriquecimento](docs/ingestion.md)
- [Indexação e recuperação vetorial](docs/vector_store.md)
- [Metodologia e resultados da avaliação RAG](docs/rag_evaluation.md)
- [Detalhes da interface FIAP](README_UI.md)

## Referências

1. OLIST. [*Brazilian E-Commerce Public Dataset by Olist*](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce/data). Kaggle.
2. LEWIS, Patrick et al. [*Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*](https://arxiv.org/abs/2005.11401). *Advances in Neural Information Processing Systems*, 33, 2020.
3. KARPUKHIN, Vladimir et al. [*Dense Passage Retrieval for Open-Domain Question Answering*](https://arxiv.org/abs/2004.04906). *Proceedings of EMNLP*, 2020. (Referência conceitual sobre recuperação densa; a implementação deste projeto usa embeddings OpenAI e ChromaDB.)

---

Projeto acadêmico desenvolvido para o **Tech Challenge da Fase 4 — Pós-Tech AI Scientist, FIAP**.
