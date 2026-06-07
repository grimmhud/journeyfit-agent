---
name: journeyfit-output-training-plan-v0
description: Define o campo v0_output que o Personal Trainer deve incluir no JSON quando estiver entregando um plano de treino ao orquestrador JourneyFit. Use somente quando o personal esta gerando um plano de treino — nao para perguntas de intake ou conversas.
version: 1.0.0
author: JourneyFit
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [journeyfit, schema, output, training, plan, v0]
    category: journeyfit
---

# JourneyFit — Output: Training Plan v0

## Quando usar

Apenas quando o Personal Trainer esta respondendo ao orquestrador com um **plano de treino** (completo ou provisório).

Nao use para:
- Perguntas de intake de treino ainda sem plano gerado
- Respostas conversacionais diretas ao usuario
- Criar um segundo treino quando `shared.plan_status.has_training_plan` for true; nesse caso, ajuste ou explique o treino salvo.

## Continuidade do treino salvo

Se o contexto do orquestrador trouxer `shared.plan_status.has_training_plan: true`,
o Personal Trainer deve trabalhar em cima do treino atual. Nao gere outro plano
paralelo, nao reinicie a periodizacao e nao troque a divisao semanal inteira sem
pedido explicito de substituicao.

Quando precisar ver o conteudo do treino salvo, chame `journeyfit_current_plan`
com `domain: "training"`. O orquestrador deve passar apenas status abstrato,
nao o treino inteiro.

Use o v0 apenas quando a resposta realmente for uma revisao renderizavel do
treino salvo. Para duvidas, explicacoes, pequenos ajustes ou check-ins, responda
no schema interno sem criar novo `v0_output.training`.

## Campo obrigatorio: v0_output

Sempre inclua no JSON de resposta ao orquestrador.

```json
{
  "v0_output": {
    "notice": {
      "agent": "personal_trainer",
      "type": "warning | info | restriction",
      "severity": "high | moderate | low",
      "message": "frase unica legivel no app sobre o plano de treino"
    },
    "training": {
      "status": "ready | provisional | unavailable",
      "split": "nome da divisao ex: Upper/Lower 4x",
      "weekly_frequency": 4,
      "session_duration_minutes": { "min": 60, "max": 85 },
      "sessions": [
        {
          "id": "day_1_upper_a",
          "name": "Superiores A",
          "focus": "Empurrar + Puxar horizontal, bracos",
          "estimated_duration_minutes": 70,
          "exercises": [
            {
              "name": "nome do exercicio",
              "sets": 4,
              "reps": "5-8",
              "rest_seconds": 120,
              "rir": "1-3",
              "note": "instrucao curta de execucao ou substituicao, ou null"
            }
          ]
        }
      ]
    },
    "follow_up_questions": [
      { "id": "t1", "question": "...", "priority": "high | medium" }
    ]
  }
}
```

## Regras de preenchimento

**status:**
- `ready` — objetivo, equipamentos e dias confirmados; plano definitivo
- `provisional` — falta objetivo, equipamentos ou dias; plano e base conservadora
- `unavailable` — restricao medica impede qualquer treino no momento

**sessions:**
- Todas as sessoes da semana devem estar presentes
- Cada sessao com todos os exercicios completos
- `id` em snake_case unico por sessao (ex: `day_1_upper_a`, `day_2_lower_a`)
- `focus` descricao curta do foco muscular da sessao

**exercises (formato obrigatorio):**
- `reps` sempre string: `"5-8"`, `"8-12"`, `"10-15/perna"`, `"30-60s"` — **nunca** `"5_a_8"` ou numero inteiro
- `rir` sempre string `"1-3"` ou `null` para exercicios tecnicos (prancha, respiracao, etc.)
- `note` sempre string ou `null` — **nunca** string vazia `""`

**follow_up_questions:**
- Apenas perguntas que mudariam selecao de exercicios, volume ou divisao semanal
- Nao duplicar: objetivo (medico pode ja ter perguntado), medicacoes (medico), alimentacao (nutricionista)
- Maximo 4 perguntas

**notice.message:**
- Frase unica sobre o estado atual do plano de treino
- Exemplos: "Plano provisorio — equipamentos ainda nao confirmados; exercicios podem precisar de substituicao."
- Exemplos: "Plano upper/lower 4x montado para o seu perfil e objetivo."
