---
name: journeyfit-output-nutrition-plan-v0
description: Define o campo v0_output que o Nutricionista deve incluir no JSON quando estiver entregando um plano alimentar ao orquestrador JourneyFit. Use somente quando o nutricionista esta gerando orientacao nutricional — nao para perguntas de intake ou conversas.
version: 1.0.0
author: JourneyFit
license: MIT
platforms: [linux, macos, windows]
metadata:
  hermes:
    tags: [journeyfit, schema, output, nutrition, plan, v0]
    category: journeyfit
---

# JourneyFit — Output: Nutrition Plan v0

## Quando usar

Apenas quando o Nutricionista esta respondendo ao orquestrador com um **plano alimentar** (completo ou provisório).

Nao use para:
- Perguntas de intake alimentar ainda sem plano gerado
- Respostas conversacionais diretas ao usuario
- Criar uma segunda dieta quando `shared.plan_status.has_nutrition_plan` for true; nesse caso, ajuste ou explique a dieta salva.

## Continuidade da dieta salva

Se o contexto do orquestrador trouxer `shared.plan_status.has_nutrition_plan: true`,
o Nutricionista deve trabalhar em cima da dieta atual. Nao gere outro plano
paralelo, nao reinicie metas e nao troque macros ou estrutura de refeicoes sem
pedido explicito de substituicao.

Quando precisar ver o conteudo da dieta salva, chame `journeyfit_current_plan`
com `domain: "nutrition"`. O orquestrador deve passar apenas status abstrato,
nao a dieta inteira.

Use o v0 apenas quando a resposta realmente for uma revisao renderizavel da
dieta salva. Para duvidas, substituicoes, pequenos ajustes ou check-ins,
responda no schema interno sem criar novo `v0_output.nutrition`.

## Campo obrigatorio: v0_output

Sempre inclua no JSON de resposta ao orquestrador.

```json
{
  "v0_output": {
    "notice": {
      "agent": "nutritionist",
      "type": "warning | info | restriction",
      "severity": "high | moderate | low",
      "message": "frase unica legivel no app sobre o plano alimentar"
    },
    "nutrition": {
      "status": "ready | provisional | unavailable",
      "kcal": { "min": 2300, "max": 2700 },
      "macros": {
        "protein_g_per_kg": { "min": 1.6, "max": 2.2 },
        "carbs_g_per_kg": { "min": 3.0, "max": 5.0 },
        "fat_g_per_kg": { "min": 0.6, "max": 1.0 }
      },
      "meals_per_day": { "min": 3, "max": 5 },
      "hydration_ml_per_kg": { "min": 30, "max": 40 },
      "timing": {
        "pre_workout_window": "60-150 min antes",
        "post_workout_window": "ate 2h depois"
      },
      "meal_examples": {
        "breakfast": ["opcao 1", "opcao 2"],
        "lunch_dinner": ["opcao 1", "opcao 2"],
        "snacks": ["opcao 1", "opcao 2"],
        "pre_workout": ["opcao 1"],
        "post_workout": ["opcao 1"]
      }
    },
    "follow_up_questions": [
      { "id": "n1", "question": "...", "priority": "high | medium" }
    ]
  }
}
```

## Regras de preenchimento

**status:**
- `ready` — objetivo, preferencias e rotina suficientes para plano personalizado
- `provisional` — falta objetivo principal, horarios ou preferencias; plano e base conservadora
- `unavailable` — restricao clinica impede qualquer orientacao nutricional

**kcal e macros:**
- Sempre faixas min/max — nunca valor unico
- `kcal` em kcal/dia absoluto (ex: 2300-2700)
- Macros em g/kg de peso corporal

**meal_examples:**
- Pelo menos 2 itens em cada categoria quando houver contexto suficiente
- Arrays vazios apenas quando o contexto for insuficiente para sugerir opcoes
- Itens devem ser frases curtas e praticas (ex: "Arroz, feijao, frango e salada")

**follow_up_questions:**
- Apenas perguntas que mudariam a estrategia calorica, macros ou exemplos de refeicao
- Nao duplicar perguntas de objetivo (medico ou personal trainer podem ja ter feito)
- Maximo 4 perguntas

**notice.message:**
- Frase unica sobre o estado atual do plano alimentar
- Exemplos: "Metas provisorias — objetivo principal ainda nao informado."
- Exemplos: "Plano alimentar personalizado para emagrecimento com suas preferencias."
