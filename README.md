# 💰 Controle de Gastos

Sistema web de controle financeiro mensal, desenvolvido como projeto pessoal para consolidar conhecimentos em **Python, PostgreSQL, APIs, autenticação, cloud e Inteligência Artificial aplicada ao desenvolvimento**.

O projeto nasceu a partir de um esboço próprio da interface e das regras de negócio. A solução foi evoluída de forma iterativa, utilizando IA generativa como ferramenta de apoio durante arquitetura, implementação, testes, revisão de código e desenvolvimento da interface.

---

## 🚀 Demonstração

A aplicação possui um **Modo Demonstração** público, que permite testar as principais funcionalidades sem necessidade de cadastro.

> 🧪 Os dados utilizados no modo DEMO são fictícios e não são persistidos no banco de dados.

🔗 **Aplicação:**  
`(https://controlegastos-bx.lovable.app/)`

No sistema, basta clicar em:

**Ver demonstração**

---

## 🖥️ Visão geral

O sistema permite controlar os gastos de forma mensal, separando:

- Gastos fixos
- Cartões de crédito
- Renda mensal
- Total de gastos
- Saldo disponível
- Data de cada lançamento

Também possui suporte a múltiplos usuários, mantendo os dados financeiros de cada conta isolados.

---

## ✨ Funcionalidades

### Financeiro

- Cadastro de renda mensal
- Cadastro de gastos fixos
- Cadastro de valores de cartões de crédito
- Data do gasto
- Edição de lançamentos
- Exclusão de lançamentos
- Cálculo automático do total de gastos
- Cálculo automático do saldo disponível
- Consulta por mês e ano

### Usuários e segurança

- Login com usuário e senha
- Autenticação por JWT
- Senhas armazenadas com hash bcrypt
- Tokens Bearer nas requisições protegidas
- Separação dos dados por usuário
- Sessão com expiração
- Proteção dos endpoints da API

### Demonstração pública

- Acesso sem usuário e senha
- Dados fictícios
- Inclusão, edição e exclusão simuladas
- Alteração de renda
- Navegação entre meses
- Dados mantidos somente no estado local do frontend
- Ao atualizar a página, os dados originais da demonstração são restaurados
- Nenhuma comunicação com o banco real durante o modo DEMO

---

## 🏗️ Arquitetura

```mermaid
flowchart TD

    A[Lovable<br/>React + TypeScript] -->|HTTPS / REST API| B[FastAPI<br/>Python]

    B --> C[Autenticação<br/>JWT + bcrypt]

    B -->|SQL| D[(PostgreSQL<br/>Neon)]

    E[Render] --> B

    F[Usuário autenticado] --> A

    G[Modo DEMO] --> H[Estado local React<br/>Sem persistência]

    H -. não acessa .-> D
