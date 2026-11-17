# Voice of Customer Intelligence com RAG

**Tech Challenge — Fase 4 | FIAP Pós-Tech — AI Scientist**

Solução de Inteligência Artificial Generativa baseada em *Retrieval-Augmented Generation* (RAG) para análise de avaliações de clientes do e-commerce brasileiro.

**Status:** Em desenvolvimento.

## 1. Visão geral

O projeto tem como objetivo transformar avaliações textuais de consumidores em uma base de conhecimento inteligente e consultável por meio de perguntas em linguagem natural.

A solução utilizará técnicas de Processamento de Linguagem Natural (PLN), embeddings e recuperação semântica para identificar informações relevantes nos comentários dos clientes e gerar respostas fundamentadas em evidências.

## 2. Problema de negócio

Empresas de e-commerce recebem milhares de avaliações contendo elogios, reclamações e percepções sobre a experiência de compra.

Embora indicadores quantitativos permitam acompanhar a satisfação dos consumidores, grande parte das informações relevantes está presente em comentários textuais não estruturados.

O desafio consiste em permitir que gestores e analistas explorem esses conteúdos de forma eficiente, identificando padrões, problemas recorrentes e oportunidades de melhoria.

## 3. Objetivos

- Construir uma base de conhecimento a partir de avaliações reais de consumidores.
- Implementar um pipeline RAG com recuperação semântica.
- Permitir consultas em linguagem natural sobre a experiência dos clientes.
- Gerar respostas fundamentadas nas avaliações recuperadas.
- Apresentar evidências que permitam rastrear os insights gerados.
- Reconhecer perguntas fora do escopo ou sem evidências suficientes.
- Avaliar a qualidade da recuperação e das respostas.

## 4. Dataset

Será utilizado o **Brazilian E-Commerce Public Dataset by Olist**, disponibilizado publicamente no Kaggle.

O conjunto contém informações de aproximadamente 100 mil pedidos realizados entre 2016 e 2018, incluindo avaliações, produtos, pagamentos e entregas.

O foco principal será a análise das avaliações textuais dos consumidores.

**Fonte:** https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce/data

## 5. Arquitetura proposta

O pipeline será desenvolvido seguindo o fluxo:

1. Recebimento da pergunta do usuário.
2. Processamento da consulta e geração de embeddings.
3. Recuperação semântica das avaliações relevantes.
4. Seleção e organização das evidências.
5. Construção do contexto para o modelo de linguagem.
6. Geração de uma resposta fundamentada nos documentos recuperados.
7. Apresentação das evidências utilizadas.

A arquitetura e suas decisões técnicas serão detalhadas conforme a evolução do projeto.

## 6. Tecnologias previstas

| Componente | Tecnologia |
|---|---|
| Linguagem | Python |
| Manipulação de dados | Pandas |
| Orquestração RAG | LangChain |
| Embeddings | A definir |
| Banco vetorial | A definir |
| Modelo de linguagem | A definir |
| Interface | Streamlit |
| Versionamento | Git e GitHub |

As escolhas serão validadas e justificadas durante o desenvolvimento.

## 7. Organização do repositório

- `data/raw/`: dados originais.
- `data/processed/`: dados preparados para utilização.
- `notebooks/`: exploração e experimentação.
- `src/ingestion/`: processamento e ingestão dos documentos.
- `src/rag/`: componentes do pipeline RAG.
- `src/evaluation/`: avaliação da solução.
- `app/`: interface da aplicação.
- `tests/`: testes automatizados.
- `docs/`: documentação técnica e arquitetura.

## 8. Exemplos de perguntas

A solução deverá permitir investigar questões como:

- Quais são os principais problemas relatados pelos clientes?
- Quais reclamações estão relacionadas à entrega?
- O que os consumidores mais elogiam?
- Quais padrões aparecem nas avaliações com notas baixas?
- Quais avaliações sustentam determinado insight?

## 9. Execução

As instruções de instalação, configuração e execução serão adicionadas após a implementação dos componentes da solução.

## 10. Referências

- OLIST. *Brazilian E-Commerce Public Dataset by Olist*. Kaggle. https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
- LEWIS, Patrick et al. *Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks*. NeurIPS, 2020. https://arxiv.org/abs/2005.11401

---

**Projeto acadêmico desenvolvido para o Tech Challenge da Fase 4 da Pós-Tech em AI Scientist da FIAP.**