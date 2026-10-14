# Radar Tributário — Grupo Dicon
### Guia de instalação e uso · Departamento Fiscal

Este guia foi escrito para quem **não é da área de tecnologia**. Siga na ordem e marque cada passo como feito.

---

## 1. O que é cada coisa

O Radar tem duas partes:

- **O painel** (`index.html`) — é o "site" que a equipe abre. Mostra as notícias em cartões coloridos por impacto, os filtros, o relógio, o boletim do dia e o placar da Reforma Tributária.
- **O robô** (`radar_fiscal.py`) — todo dia às 8h ele visita as fontes (Receita, PGFN, Fazenda, Câmara, Senado, MAPA, CFC, Portal Contábeis, Jornal Contábil e as SEFAZ dos 27 estados), separa o que importa, classifica e **atualiza o painel sozinho**. Se você quiser, também manda o boletim por e-mail.

### Arquivos da pasta

| Arquivo | Para que serve |
|---|---|
| `index.html` | O painel. Dois cliques abrem no navegador. |
| `destaques.json` | Atos importantes fixados pela equipe na faixa "Fique de olho". |
| `logo.png` e `logo-icone.png` | Sua logo (topo do painel e ícone da aba). |
| `radar_fiscal.py` | O robô que busca as notícias. |
| `requirements.txt` | Lista de componentes que o robô precisa. |
| `instalar.bat` | Instala os componentes (só uma vez). |
| `executar_radar.bat` | Busca as notícias **agora** e abre o painel. |
| `iniciar_automatico.bat` | Deixa o robô ligado, buscando todo dia às 8h. |
| `.github/workflows/radar.yml` | Faz o robô rodar sozinho "na nuvem" (Opção A abaixo). |
| `noticias.json` e `radar.log` | Criados pelo robô: a memória das notícias e o diário do que ele fez. |

> Na primeira vez que você abrir o painel ele aparece em **modo demonstração**, com notícias de exemplo marcadas como "[Exemplo]". Elas somem assim que o robô roda pela primeira vez.

---

## 2. Qual caminho escolher?

Você quer que a equipe apenas **clique num link**. Há dois jeitos de chegar lá:

| | **Opção A — Tudo no GitHub** ⭐ recomendada | **Opção B — Robô no seu computador** |
|---|---|---|
| Precisa deixar o computador ligado às 8h? | **Não** | Sim |
| Instalar programas? | Não | Sim (Python) |
| Custo | Gratuito | Gratuito |
| Link para a equipe | Sim | Sim |

O **GitHub** é um site gratuito que guarda arquivos e consegue publicá-los como página de internet (o recurso chama "GitHub Pages"). Ele também consegue rodar o robô todo dia sozinho.

---

## 3. Opção A — Tudo no GitHub (sem computador ligado)

### Passo A1 · Criar a conta
1. Entre em **github.com** e clique em **Sign up**.
2. Crie a conta com o e-mail da empresa. Escolha um nome de usuário simples, por exemplo `grupodicon` — ele vai aparecer no link.

### Passo A2 · Criar o "repositório" (a pasta online)
1. Já logado, clique no **+** no canto superior direito → **New repository**.
2. Em *Repository name* escreva: `radar-dicon`
3. Marque **Public** (o GitHub Pages gratuito exige pasta pública — ver aviso de privacidade no fim deste passo).
4. Clique em **Create repository**.

### Passo A3 · Enviar os arquivos
1. Na página que abriu, clique no link **uploading an existing file**.
2. Abra a pasta do Radar no seu computador, **selecione tudo** (Ctrl + A) — inclusive a pasta `.github` — e arraste para a janela do navegador.
3. Espere carregar e clique no botão verde **Commit changes**.
4. Confira se a pasta `.github` apareceu na lista. Se **não** apareceu:
   - Clique em **Add file → Create new file**.
   - No nome, digite exatamente: `.github/workflows/radar.yml`
   - Abra o arquivo `radar.yml` do seu computador com o Bloco de Notas, copie tudo e cole no GitHub.
   - Clique em **Commit changes**.

### Passo A4 · Ligar o site
1. No repositório, clique em **Settings** (engrenagem, no menu de cima).
2. No menu da esquerda, clique em **Pages**.
3. Em *Branch*, escolha **main** e a pasta **/ (root)** → **Save**.
4. Aguarde 1 a 2 minutos e atualize a página. Vai aparecer: **"Your site is live at…"**
   O link será parecido com: `https://grupodicon.github.io/radar-dicon/`
5. **Esse é o link que você manda para a equipe.** Eles só clicam e o painel abre — no computador ou no celular.

### Passo A5 · Deixar o robô trabalhar sozinho
1. Ainda em **Settings**, menu da esquerda: **Actions → General**.
2. Em *Workflow permissions*, marque **Read and write permissions** → **Save**.
3. Vá na aba **Actions** (menu de cima). Se aparecer um botão verde de autorização, clique para ativar.
4. Clique em **Radar Tributário diário** → **Run workflow** → **Run workflow**. Isso faz a primeira busca na hora.
5. Em 3 a 6 minutos aparece um ✅ verde. Abra o link do painel: as notícias reais já estarão lá e o aviso de "modo demonstração" some.

A partir daí, **todo dia às 8h** o GitHub busca as notícias e atualiza o site. O painel da equipe se atualiza sozinho a cada 30 minutos (ou ao apertar F5).

> O GitHub às vezes atrasa alguns minutos o horário agendado em dias de muito movimento. É normal.

> **Privacidade:** no plano gratuito, a página e os arquivos ficam públicos (quem tiver o link consegue ver). Como o painel só reúne notícias públicas, isso não costuma ser problema. **Nunca** coloque senhas dentro dos arquivos — use os "segredos" explicados abaixo.

### Passo A6 · (Opcional) Boletim por e-mail todo dia
Se o e-mail for Gmail, primeiro crie uma **senha de app**:
1. Entre em **myaccount.google.com** → **Segurança** → ative a **Verificação em duas etapas** (se ainda não estiver).
2. Na busca da conta Google, digite **Senhas de app**, crie uma com o nome "Radar" e **copie a senha de 16 letras**.

Agora guarde as informações no GitHub, de forma protegida:
1. No repositório: **Settings → Secrets and variables → Actions → New repository secret**.
2. Crie um segredo por vez (nome à esquerda, valor à direita):

| Nome do segredo | O que colocar |
|---|---|
| `DICON_EMAIL_ATIVO` | `sim` |
| `DICON_EMAIL_USUARIO` | o e-mail que vai enviar (ex.: radar.dicon@gmail.com) |
| `DICON_EMAIL_SENHA` | a senha de app de 16 letras |
| `DICON_EMAIL_PARA` | os e-mails da equipe, separados por vírgula |
| `DICON_LINK_PAINEL` | o link do site (Passo A4), para aparecer o botão "Abrir o painel" no e-mail |

Pronto: no próximo dia às 8h a equipe recebe o boletim.

---

## 4. Opção B — Robô no seu computador (Windows)

### Passo B1 · Instalar o Python (uma vez só)
1. Entre em **python.org/downloads** e clique no botão amarelo **Download Python**.
2. Abra o arquivo baixado.
3. ⚠️ **Muito importante:** na primeira tela, marque a caixinha **"Add python.exe to PATH"** lá embaixo.
4. Clique em **Install Now** e aguarde terminar.

### Passo B2 · Preparar a pasta
1. Coloque a pasta do Radar num lugar fixo, por exemplo `C:\RadarDicon`.
2. Dê dois cliques em **`instalar.bat`**. Uma janela preta aparece, instala tudo e diz "Pronto!". Pode fechar.

### Passo B3 · Testar
1. Dê dois cliques em **`executar_radar.bat`**.
2. A janela mostra cada fonte sendo consultada (leva de 3 a 6 minutos).
3. No fim, o painel abre no navegador com as notícias reais.

### Passo B4 · Agendar para todo dia às 8h
**Jeito mais simples:** dê dois cliques em `iniciar_automatico.bat` e deixe a janela aberta (pode minimizar). Às 8h ele busca sozinho.

**Jeito mais caprichado** (liga sozinho mesmo depois de reiniciar o computador):
1. Aperte a tecla **Windows**, digite **Agendador de Tarefas** e abra.
2. À direita, clique em **Criar Tarefa Básica…**
3. Nome: `Radar Tributário` → **Avançar**.
4. Disparador: **Diariamente** → **Avançar** → horário **08:00:00** → **Avançar**.
5. Ação: **Iniciar um programa** → **Avançar**.
6. Em *Programa/script*, clique em **Procurar** e escolha o arquivo `executar_radar.bat` da pasta do Radar.
7. Em *Iniciar em*, cole o endereço da pasta (ex.: `C:\RadarDicon`).
8. **Avançar → Concluir**.

> O computador precisa estar ligado às 8h. Se ele estiver desligado, rode o `executar_radar.bat` quando chegar.

### Passo B5 · Colocar o painel como site para a equipe
Faça os Passos **A1, A2, A3 e A4** da Opção A (pode pular a pasta `.github`). Depois, para o seu computador enviar o painel atualizado ao site todo dia:

1. No GitHub, clique na sua foto (canto superior direito) → **Settings** → no fim do menu, **Developer settings** → **Personal access tokens → Fine-grained tokens → Generate new token**.
2. Nome: `Radar`. Validade: 1 ano. Em *Repository access* escolha **Only select repositories** → `radar-dicon`.
3. Em *Permissions → Repository permissions → Contents*, escolha **Read and write**.
4. **Generate token** e copie o código (começa com `github_pat_`).
5. Guarde no Windows (sem deixar no arquivo): aperte **Windows**, digite **variáveis de ambiente**, abra **Editar as variáveis de ambiente para sua conta** → **Novo…** e crie:
   - `DICON_GITHUB_TOKEN` = o código copiado
   - `DICON_GITHUB_REPO` = `seuusuario/radar-dicon` (troque pelo seu usuário)
6. Abra `radar_fiscal.py` com o Bloco de Notas, procure a linha `PUBLICAR_GITHUB = False` e troque para `PUBLICAR_GITHUB = True`. Salve.

Pronto: toda vez que o robô rodar, o site da equipe é atualizado.

### Passo B6 · (Opcional) E-mail na Opção B
1. Crie a senha de app do Gmail (ver Passo A6).
2. Crie as variáveis de ambiente (mesmo caminho do Passo B5, item 5): `DICON_EMAIL_USUARIO`, `DICON_EMAIL_SENHA`, `DICON_EMAIL_PARA` e, se quiser, `DICON_LINK_PAINEL`.
3. No `radar_fiscal.py`, troque `EMAIL_ATIVO = False` por `EMAIL_ATIVO = True`.

---

## 5. Usando o painel no dia a dia

- **Menu de cima:** Radar do Dia (tudo), Reforma Tributária, Fiscal (ST, NCM, prazos, vencimentos, obrigações), Federal, Estadual, Municipal e Internacional. O número ao lado mostra quantas notícias há em cada um.
- **Cores dos cartões:** 🔴 **Alto** = pede ação da equipe · 🟠 **Médio** = vale acompanhar · 🟢 **Baixo** = para conhecimento.
- **"Por que importa"**: frase simples dizendo o que a notícia muda na prática.
- **Filtros (coluna da esquerda; no celular, botão ⚙ Filtros):** esfera, impacto, data (Hoje, 3, 7, 30 dias ou um período escolhido), tipo de fonte, estado e assuntos (Exclusão da ST, NCM, Prazo, Nova obrigação, Vencimento…). Clicar numa etiqueta de um cartão também filtra.
- **Quadro dos 27 estados:** os 12 estados em foco aparecem destacados com um ponto. Clique num estado para ver só as notícias dele.
- **Boletim do dia** (botão azul): resumo pronto com números, alertas, prazos e Reforma. Tem botões para **copiar** (colar no WhatsApp/Teams) e **imprimir ou salvar em PDF**.
- **Relógio e "Última atualização":** ponto verde = robô rodou nas últimas 26 horas; ponto laranja = está atrasado, vale conferir.
- **Placar da Reforma:** IBS, CBS e Imposto Seletivo, com fase atual, próxima etapa e contagem de dias. Ele segue o calendário da Emenda Constitucional 132/2023 e da Lei Complementar 214/2025 e **avança sozinho** conforme as datas passam.
- **Lua no topo:** alterna entre tema escuro e claro (cada pessoa escolhe o seu).

> Os resumos são automáticos. Antes de aplicar qualquer mudança num cliente, clique em **"Ler na fonte"** e confira o texto oficial.

---

## 6. Atos fixados — a faixa "📌 Fique de olho"

O robô busca o que foi publicado **nos últimos dias**. Um ato publicado meses antes e que entra em vigor agora (como a Portaria SRE 34/2026, publicada em junho e válida desde 01/10) precisa ser **fixado** pela equipe. Ele aparece no topo do painel, com a contagem de dias até a vigência (ou "em vigor desde"), e também no boletim.

**Para fixar um ato no GitHub:**
1. Na aba **Code**, abra o arquivo `destaques.json` e clique no **lápis** (editar).
2. Copie o bloco inteiro do exemplo que já está lá, do `{` até o `}`.
3. Coloque uma **vírgula** depois do `}` do último bloco e cole o bloco novo em seguida.
4. Troque os textos. Os campos mais importantes são:
   - `titulo`: frase curta do que mudou.
   - `porque`: o que a equipe precisa fazer.
   - `link`: endereço do ato.
   - `uf`: sigla do estado (deixe `""` se for federal) e `esfera`: `Federal`, `Estadual` ou `Municipal`.
   - `publicado_em`, `vigencia` e `fixar_ate`: datas no formato `2026-10-01`. O ato sai do painel sozinho depois de `fixar_ate`.
5. Clique em **Commit changes**. O painel mostra o ato na próxima execução do robô. Para ver na hora, rode o robô pelo botão **Run workflow** (Passo A5).

> Se o painel deixar de mostrar os fixados depois de uma edição, quase sempre é uma vírgula ou aspas faltando. O registro da execução avisa: "destaques.json com erro de digitação".

**Legislação de SP direto da fonte:** além das notícias, o robô lê todo dia o **portal de legislação da SEFAZ-SP** (portarias, decretos, comunicados e respostas à consulta) dos últimos 15 dias, mesmo que o ato não tenha virado notícia. Para não receber as Respostas à Consulta, troque `INCLUIR_RESPOSTAS_CONSULTA = True` por `False` no `radar_fiscal.py`.

## 7. Ajustes que você pode fazer sozinho(a)

Abra `radar_fiscal.py` com o Bloco de Notas. Tudo o que pode ser mudado está no começo, no quadro **"CONFIGURAÇÕES — PODE EDITAR AQUI"**:

- `HORARIO_DIARIO` — horário da busca no modo automático do computador.
- `ESTADOS_FOCO` — os estados que recebem mais atenção.
- `LIMITE_ESTADO_FOCO` / `LIMITE_ESTADO_COMUM` — quantas notícias buscar por estado.
- `DIAS_NO_PAINEL` — por quantos dias as notícias ficam no painel (padrão: 30).
- Mais abaixo, em **"REGRAS DE CLASSIFICAÇÃO"**, você pode incluir palavras novas em cada assunto e mudar as frases de "Por que importa".

Na Opção A, faça a alteração direto no GitHub: abra o arquivo `radar_fiscal.py` no repositório, clique no **lápis** (editar), altere e clique em **Commit changes**.

**Horário na Opção A:** fica no arquivo `.github/workflows/radar.yml`, na linha `cron: "0 11 * * *"`. O GitHub usa o horário de Londres: **11 = 8h de Brasília**. Para 7h, use `0 10 * * *`.

**Resumos ainda mais simples (opcional):** se você tiver uma chave da API do Claude (console.anthropic.com), crie o segredo/variável `ANTHROPIC_API_KEY`. O robô passa a reescrever os resumos das notícias de alto e médio impacto em linguagem bem simples. Sem a chave, ele usa o resumo da própria fonte. Há um custo por uso na API, limitado a 40 resumos por dia na configuração padrão.

---

## 8. Se algo der errado

| O que aconteceu | O que fazer |
|---|---|
| Janela preta diz "python não é reconhecido" | O Python foi instalado sem marcar "Add to PATH". Reinstale marcando a caixinha (Passo B1). |
| "Faltam componentes" | Dê dois cliques em `instalar.bat`. |
| Painel continua em "modo demonstração" | O robô ainda não rodou. Opção A: Actions → Run workflow. Opção B: `executar_radar.bat`. |
| Ponto laranja em "Última atualização" | O robô não rodou nas últimas 26h. Opção A: veja a aba Actions (❌ vermelho = clique para ver o motivo). Opção B: o computador estava desligado às 8h? |
| Uma fonte aparece com 0 notícias | Normal em dias sem novidade. Se ficar zerada por vários dias, o site da fonte pode ter mudado; o robô usa uma busca reserva no Google Notícias, então as notícias continuam chegando. |
| E-mail não chega | Confira se usou a **senha de app** (não a senha normal do Gmail) e veja a caixa de spam. |
| Logo não aparece | O arquivo precisa se chamar exatamente `logo.png` e estar na mesma pasta do `index.html`. Se não houver logo, aparece "Grupo Dicon" escrito. |
| Quero ver o que o robô fez | Abra o arquivo `radar.log` (Opção B) ou o registro da execução na aba Actions (Opção A). |

**Teste sem mexer no painel:** abra o Prompt de Comando na pasta e digite `python radar_fiscal.py --teste`. Ele mostra as notícias encontradas e a classificação, sem alterar nada.

---

*Radar Tributário · Grupo Dicon · Departamento Fiscal*
