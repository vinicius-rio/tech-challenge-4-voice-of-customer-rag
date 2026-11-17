# Avaliação do pipeline RAG — Olist

## 1. Objetivo

Avaliar a capacidade do pipeline RAG de produzir respostas
fundamentadas nas avaliações dos consumidores da Olist,
reconhecendo ausência de evidências e divergências entre
comentários e metadados.

## 2. Configuração

- Base textual: 42.687 avaliações.
- Embeddings: text-embedding-3-small.
- Banco vetorial: ChromaDB.
- Modelo gerador: gpt-4.1-mini.
- Recuperação: similaridade de cosseno, top-k e filtros.
- Cenários de avaliação: 6.

## 3. Metodologia

A avaliação foi realizada em duas camadas:

1. Verificações automáticas: estrutura das respostas,
   validade das referências e heurísticas de abstenção.
2. Revisão humana: comparação entre afirmações geradas,
   comentários originais e metadados dos pedidos.

As verificações automáticas não medem diretamente
faithfulness, precisão factual ou recall do retriever.

## 4. Resultados iniciais

| Caso | Automático | Revisão humana |
|---|---|---|
| E01 - Produtos quebrados | Aprovado | Parcial |
| E02 - Causa desconhecida | Aprovado | Adequado |
| E03 - Lucro líquido | Aprovado | Adequado |
| E04 - Reclamações de atraso | Aprovado | Parcial |
| E05 - Atraso confirmado | Aprovado | Parcial |
| E06 - Previsão do tempo | Aprovado | Adequado, com ressalva |

Resumo:
- Aprovação automática: 6/6.
- Erros de execução: 0.
- Respostas adequadas na revisão inicial: 3/6.
- Respostas com ressalvas: 3/6.
- Tokens de entrada na avaliação: 6.220.
- Tokens de saída na avaliação: 952.

Os números representam apenas os seis cenários avaliados.
Não devem ser interpretados como desempenho geral do sistema.

## 5. Principais achados

### 5.1. Generalização indevida

No E01, o modelo produziu uma conclusão excessiva
sobre a relação entre avarias e prazo de entrega.

A auditoria confirmou que os cinco pedidos recuperados
foram entregues antes das respectivas datas previstas.

### 5.2. Comentários versus metadados

No E04, os dados de atraso e o status "processing"
mencionados na resposta foram confirmados no ChromaDB.

No E05, um cliente afirmou ter recebido o pedido
dentro do prazo, enquanto o campo estruturado
registrava 112 dias de atraso.

Os dados disponíveis não explicam a divergência.

### 5.3. Abstenção

Nos casos E03 e E06, o modelo reconheceu corretamente
que os documentos recuperados não permitiam responder
às perguntas sobre lucro líquido e previsão do tempo.

### 5.4. Limitações dos metadados

O status do pedido pode representar sua situação final,
que não necessariamente corresponde ao momento da
avaliação escrita pelo cliente.

O campo de atraso também não permite, isoladamente,
inferir causas de insatisfação ou de danos aos produtos.

## 6. Melhorias implementadas

O prompt do gerador foi reforçado para:

- Evitar inferências causais sem evidência.
- Diferenciar comentários e metadados.
- Explicitar divergências entre fontes.
- Não extrapolar pequenas amostras.
- Reconhecer informações insuficientes.
- Respeitar a dimensão temporal dos registros.

## 7. Teste controlado após as melhorias

Foi isolado um documento do E05 com:

- Comentário: entrega dentro do prazo.
- Metadado: 112 dias de atraso.
- Status armazenado: delivered.

O retriever foi substituído por uma resposta controlada,
mantendo a chamada real ao modelo gerador.

Resultado: o modelo identificou a divergência, citou a
fonte e afirmou que seriam necessários dados adicionais
para explicá-la.

Consumo na geração:
- Entrada: 754 tokens.
- Saída: 205 tokens.

O teste direcionado passou, mas não substitui uma
nova avaliação integral dos seis cenários.

## 8. Reprodutibilidade

Executar os testes unitários:

    python -m unittest discover -s tests -p "test_rag_generation.py" -v

Validar os casos sem chamar a API:

    python -m src.evaluation.evaluate_rag --dry-run

Executar a avaliação completa:

    python -m src.evaluation.evaluate_rag

A execução completa realiza chamadas pagas à OpenAI.

## 9. Limitações e trabalhos futuros

- Amostra de avaliação pequena, com apenas seis perguntas.
- Verificações automáticas predominantemente heurísticas.
- Ausência de conjunto rotulado para Recall@k e Precision@k.
- Respostas do LLM sujeitas a variações entre execuções.
- Necessidade de avaliar sistematicamente a versão
  mais recente do prompt.
- Necessidade de auditoria temporal dos pedidos quando
  houver divergências relevantes.

## 10. Conclusão

O pipeline demonstrou capacidade inicial de responder
com referências, reconhecer limitações das fontes e
identificar conflitos entre comentários e metadados.

A revisão humana identificou imprecisões não capturadas
pelas verificações automáticas, reforçando a importância
da avaliação de fundamentação em sistemas RAG.
