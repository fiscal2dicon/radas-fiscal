# -*- coding: utf-8 -*-
"""
RADAR TRIBUTÁRIO — GRUPO DICON · Departamento Fiscal
====================================================
Robô que busca notícias tributárias, classifica cada uma
(esfera, impacto e assuntos) e atualiza o painel (index.html).

Como usar (veja o README.md para o passo a passo completo):
    python radar_fiscal.py              -> busca as notícias agora (uma vez)
    python radar_fiscal.py --agendar    -> fica ligado e busca todo dia às 08h
    python radar_fiscal.py --sem-email  -> busca agora, mas não manda e-mail
    python radar_fiscal.py --teste      -> mostra o que foi encontrado sem alterar o painel
"""

import argparse
import base64
import hashlib
import html
import json
import logging
import os
import re
import smtplib
import ssl
import sys
import time
import unicodedata
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from urllib.parse import quote_plus

try:
    import feedparser
    import requests
except ImportError:
    print("\n>>> Faltam componentes. Rode primeiro o arquivo 'instalar.bat' "
          "(ou: pip install -r requirements.txt)\n")
    sys.exit(1)


# ╔══════════════════════════════════════════════════════════════════╗
# ║                 CONFIGURAÇÕES — PODE EDITAR AQUI                 ║
# ╚══════════════════════════════════════════════════════════════════╝

PASTA = Path(__file__).resolve().parent
ARQUIVO_PAINEL = PASTA / "index.html"        # painel que será atualizado
ARQUIVO_HISTORICO = PASTA / "noticias.json"  # memória das notícias já coletadas
ARQUIVO_LOG = PASTA / "radar.log"

HORARIO_DIARIO = "08:00"      # horário da busca automática (modo --agendar)
DIAS_PARA_TRAS = 3            # pega notícias publicadas nos últimos X dias
DIAS_PRIMEIRA_EXECUCAO = 30   # na 1ª execução (sem histórico) busca mais para trás
DIAS_LEGISLACAO = 15          # atos do portal de legislação da SEFAZ-SP: últimos X dias
INCLUIR_RESPOSTAS_CONSULTA = True   # incluir as Respostas à Consulta (RC) da SEFAZ-SP
ARQUIVO_DESTAQUES = PASTA / "destaques.json"  # atos fixados pela equipe ("Fique de olho")
DIAS_NO_PAINEL = 30           # o painel guarda notícias dos últimos X dias
MAX_NO_PAINEL = 600           # limite de notícias no painel

# Estados com foco especial (coletam mais notícias e ganham peso no impacto)
ESTADOS_FOCO = ["SP", "RJ", "MG", "PI", "BA", "AM", "GO", "ES", "SC", "CE", "PE", "RN"]
LIMITE_ESTADO_FOCO = 15       # notícias por consulta em estado de foco
LIMITE_ESTADO_COMUM = 4       # notícias por consulta nos demais estados
LIMITE_FONTE = 20             # notícias por fonte nacional

# ---------- E-MAIL (opcional) ----------
# Deixe EMAIL_ATIVO = False para não enviar.
# Por segurança a SENHA pode ficar fora deste arquivo: crie a variável
# de ambiente DICON_EMAIL_SENHA (o README explica). Gmail exige "senha de app".
EMAIL_ATIVO = False            # troque para True para enviar o boletim
if os.getenv("DICON_EMAIL_ATIVO", "").lower() == "sim":
    EMAIL_ATIVO = True
EMAIL_SERVIDOR = "smtp.gmail.com"
EMAIL_PORTA = 465
EMAIL_REMETENTE = os.getenv("DICON_EMAIL_USUARIO", "seu.email@gmail.com")
EMAIL_SENHA = os.getenv("DICON_EMAIL_SENHA", "")
EMAIL_DESTINOS = [e.strip() for e in os.getenv(
    "DICON_EMAIL_PARA", "equipe1@empresa.com.br, equipe2@empresa.com.br").split(",") if e.strip()]
LINK_DO_PAINEL = os.getenv("DICON_LINK_PAINEL", "")   # ex.: https://seuusuario.github.io/radar-dicon/

# ---------- PUBLICAR NO SITE (opcional — ver README, "Opção B") ----------
# Envia o painel atualizado para o GitHub Pages direto do seu computador.
PUBLICAR_GITHUB = False        # troque para True (Opção B do README)
GITHUB_REPOSITORIO = os.getenv("DICON_GITHUB_REPO", "seuusuario/radar-dicon")
GITHUB_TOKEN = os.getenv("DICON_GITHUB_TOKEN", "")

# ---------- RESUMO COM INTELIGÊNCIA ARTIFICIAL (opcional) ----------
# Se existir a variável ANTHROPIC_API_KEY, os resumos são reescritos
# em linguagem bem simples pelo Claude. Sem a chave, usa o resumo da fonte.
IA_MODELO = "claude-haiku-5-5"
IA_MAX_RESUMOS = 40           # limite de resumos por execução (controla custo)


# ╔══════════════════════════════════════════════════════════════════╗
# ║                        FONTES MONITORADAS                        ║
# ╚══════════════════════════════════════════════════════════════════╝
# "rss": endereços de feed direto da fonte (testados em ordem).
# "busca": consulta de reserva no Google Notícias, usada se o feed falhar
#          e também para complementar.
# "filtrar": True = só aceita notícia com assunto tributário.

FONTES = [
    {"nome": "Receita Federal", "dominio": "gov.br/receitafederal", "tipo": "Órgão federal", "esfera": "Federal", "filtrar": False,
     "rss": ["https://www.gov.br/receitafederal/pt-br/assuntos/noticias/RSS"],
     "busca": '"Receita Federal" (tributo OR imposto OR declaração OR prazo OR IBS OR CBS)'},
    {"nome": "PGFN", "dominio": "gov.br/pgfn", "tipo": "Órgão federal", "esfera": "Federal", "filtrar": False,
     "rss": ["https://www.gov.br/pgfn/pt-br/assuntos/noticias/RSS"],
     "busca": 'PGFN (transação OR "dívida ativa" OR parcelamento OR edital)'},
    {"nome": "Ministério da Fazenda", "dominio": "gov.br/fazenda", "tipo": "Órgão federal", "esfera": "Federal", "filtrar": True,
     "rss": ["https://www.gov.br/fazenda/pt-br/assuntos/noticias/RSS"],
     "busca": '"Ministério da Fazenda" (reforma tributária OR tributo OR IBS OR CBS OR imposto)'},
    {"nome": "Câmara dos Deputados", "dominio": "camara.leg.br", "tipo": "Legislativo", "esfera": "Federal", "filtrar": True,
     "rss": ["https://www.camara.leg.br/noticias/rss/dinamico/ECONOMIA"],
     "busca": 'site:camara.leg.br ("reforma tributária" OR IBS OR CBS OR "Imposto Seletivo" OR tributação)'},
    {"nome": "Senado Federal", "dominio": "senado.leg.br", "tipo": "Legislativo", "esfera": "Federal", "filtrar": True,
     "rss": ["https://www12.senado.leg.br/noticias/feed/todasnoticias/RSS",
             "https://www12.senado.leg.br/noticias/rss"],
     "busca": 'Senado ("reforma tributária" OR IBS OR CBS OR "Imposto Seletivo" OR tributo)'},
    {"nome": "MAPA", "dominio": "gov.br/agricultura", "tipo": "Órgão federal", "esfera": "Federal", "filtrar": True,
     "rss": ["https://www.gov.br/agricultura/pt-br/assuntos/noticias/RSS"],
     "busca": '(Funrural OR "produtor rural" OR agronegócio) (tributo OR imposto OR ICMS OR "reforma tributária")'},
    {"nome": "CFC", "dominio": "cfc.org.br", "tipo": "Entidade contábil", "esfera": "Federal", "filtrar": True,
     "rss": ["https://cfc.org.br/feed/"],
     "busca": '"Conselho Federal de Contabilidade" (tributária OR reforma OR obrigação)'},
    {"nome": "Portal Contábeis", "dominio": "contabeis.com.br", "tipo": "Portal de notícias", "esfera": None, "filtrar": True,
     "rss": ["https://www.contabeis.com.br/rss/noticias/", "https://www.contabeis.com.br/rss/"],
     "busca": 'site:contabeis.com.br (ICMS OR IBS OR CBS OR prazo OR obrigação OR NCM)'},
    {"nome": "Jornal Contábil", "dominio": "jornalcontabil.com.br", "tipo": "Portal de notícias", "esfera": None, "filtrar": True,
     "rss": ["https://www.jornalcontabil.com.br/feed/"],
     "busca": 'site:jornalcontabil.com.br (ICMS OR IBS OR CBS OR prazo OR obrigação)'},
]

# Buscas por ASSUNTO — o foco do Departamento Fiscal
BUSCAS_TEMAS = [
    ("Exclusão da ST", '("substituição tributária" OR "ICMS-ST") (exclusão OR exclui OR retira OR revoga OR "deixa de")'),
    ("Reforma Tributária", '("reforma tributária" OR IBS OR CBS) (regulamentação OR "Comitê Gestor" OR alíquota OR nota fiscal)'),
    ("Imposto Seletivo", '"Imposto Seletivo"'),
    ("Alíquota", '(alíquota OR "alíquota de referência" OR redutor) (CBS OR IBS OR "Imposto Seletivo")'),
    ("Reforma Tributária", '"Comitê Gestor" IBS (resolução OR regulamento OR portaria OR publica OR aprova)'),
    ("Reforma Tributária", '(CBS OR IBS) ("nota técnica" OR "NF-e" OR "split payment" OR "Receita Federal") (publica OR divulga OR obrigatório OR prazo)'),
    ("NCM", '(NCM OR "Nomenclatura Comum do Mercosul" OR TIPI) (alteração OR novos códigos OR tabela)'),
    ("Prazo", '("obrigação acessória" OR SPED OR EFD OR DCTFWeb OR "EFD-Reinf" OR ECF OR ECD) (prazo OR prorroga OR adiado)'),
    ("Nova obrigação", '("nova obrigação acessória" OR "nova declaração" OR "passa a ser obrigatória") (fiscal OR tributária)'),
    ("Vencimento", '(ICMS OR ISS OR DARF OR tributo) ("data de vencimento" OR "altera vencimento" OR "novo vencimento")'),
    ("FUNRURAL", 'Funrural'),
]

# SEFAZ dos 27 estados: UF -> (nome do estado, site oficial)
SEFAZ = {
    "AC": ("Acre", "sefaz.ac.gov.br"), "AL": ("Alagoas", "sefaz.al.gov.br"),
    "AP": ("Amapá", "sefaz.ap.gov.br"), "AM": ("Amazonas", "sefaz.am.gov.br"),
    "BA": ("Bahia", "sefaz.ba.gov.br"), "CE": ("Ceará", "sefaz.ce.gov.br"),
    "DF": ("Distrito Federal", "economia.df.gov.br"), "ES": ("Espírito Santo", "sefaz.es.gov.br"),
    "GO": ("Goiás", "goias.gov.br/economia"), "MA": ("Maranhão", "sefaz.ma.gov.br"),
    "MT": ("Mato Grosso", "sefaz.mt.gov.br"), "MS": ("Mato Grosso do Sul", "sefaz.ms.gov.br"),
    "MG": ("Minas Gerais", "fazenda.mg.gov.br"), "PA": ("Pará", "sefa.pa.gov.br"),
    "PB": ("Paraíba", "sefaz.pb.gov.br"), "PR": ("Paraná", "fazenda.pr.gov.br"),
    "PE": ("Pernambuco", "sefaz.pe.gov.br"), "PI": ("Piauí", "sefaz.pi.gov.br"),
    "RJ": ("Rio de Janeiro", "fazenda.rj.gov.br"), "RN": ("Rio Grande do Norte", "set.rn.gov.br"),
    "RS": ("Rio Grande do Sul", "fazenda.rs.gov.br"), "RO": ("Rondônia", "sefin.ro.gov.br"),
    "RR": ("Roraima", "sefaz.rr.gov.br"), "SC": ("Santa Catarina", "sef.sc.gov.br"),
    "SP": ("São Paulo", "fazenda.sp.gov.br"), "SE": ("Sergipe", "sefaz.se.gov.br"),
    "TO": ("Tocantins", "sefaz.to.gov.br"),
}
# Se algum estado tiver feed RSS próprio, cole aqui. Ex.: "SP": ["https://..."]
SEFAZ_RSS_EXTRA = {}


# ╔══════════════════════════════════════════════════════════════════╗
# ║            REGRAS DE CLASSIFICAÇÃO (assuntos e impacto)          ║
# ╚══════════════════════════════════════════════════════════════════╝
# Palavras escritas sem acento e em minúsculas.

TAGS = {
    "Exclusão da ST": ["exclusao da substituicao", "exclusao do regime de substituicao", "exclui da substituicao",
                       "excluidos da substituicao", "retira da substituicao", "retirada da substituicao",
                       "fim da substituicao", "deixa de ser substituicao", "deixam de estar sujeitos",
                       "revoga a substituicao", "saida da st", "exclusao da st", "excluidos do regime de st",
                       "excluir da substituicao"],
    "Substituição Tributária": ["substituicao tributaria", "icms-st", "icms st", "icms/st"],
    "ICMS": ["icms", "difal"],
    "IPI": [" ipi", "ipi ", "tipi"],
    "IBS": [" ibs", "ibs ", "imposto sobre bens e servicos"],
    "CBS": [" cbs", "cbs ", "contribuicao sobre bens e servicos"],
    "Imposto Seletivo": ["imposto seletivo", "imposto do pecado"],
    "Reforma Tributária": ["reforma tributaria", "comite gestor", "lc 214", "lei complementar 214", "split payment",
                           "plp 108", "ec 132", "emenda constitucional 132", "cashback"],
    "NCM": ["ncm", "nomenclatura comum do mercosul", "tipi", "classificacao fiscal"],
    "Prazo": ["prazo", "prorroga", "prorrogacao", "adiad", "data limite", "ate o dia", "postergad"],
    "Vencimento": ["vencimento", "data de pagamento", "data de recolhimento"],
    "Obrigação acessória": ["obrigacao acessoria", "obrigacoes acessorias", "sped", "efd ", "efd-", "ecd", "ecf",
                            "dctf", "reinf", "gia", "dirf", "dime", "desif", "dmed", "declaracao",
                            "escrituracao", "bloco k"],
    "Nova obrigação": ["nova obrigacao", "novas obrigacoes", "nova declaracao", "passa a ser obrigatori",
                       "passam a ser obrigatori", "institui a declaracao", "torna obrigatori", "nova escrituracao"],
    "FUNRURAL": ["funrural", "contribuicao do produtor rural"],
    "Agro": ["agro", "produtor rural", "rural", "agricultura", "pecuaria"],
    "PIS/Cofins": ["pis", "cofins"],
    "IRPJ/CSLL": ["irpj", "csll", "imposto de renda pessoa juridica"],
    "ISS": [" iss ", " iss,", " iss.", " iss;", " iss:", "(iss", " iss)", "imposto sobre servicos", "issqn",
            "iss-"],
    "NF-e/NFS-e": ["nf-e", "nfe", "nfs-e", "nfse", "nota fiscal", "nfc-e", "ct-e", "mdf-e"],
    "Parcelamento/Transação": ["parcelamento", "transacao tributaria", "refis", "regularizacao de debitos",
                               "divida ativa", "edital de transacao", "litigio zero"],
    "Legislação estadual": ["decreto", "convenio icms", "convenio", "protocolo icms", "ajuste sinief",
                            "portaria", "resolucao", "instrucao normativa", "regulamento do icms", "ricms"],
    "Benefício fiscal": ["beneficio fiscal", "incentivo fiscal", "isencao", "reducao de base", "credito presumido",
                         "diferimento"],
    "Simples Nacional": ["simples nacional", "mei "],
    "Internacional": ["ocde", "pilar 2", "pilar dois", "dupla tributacao", "tratado", "acordo internacional",
                      "tarifa de importacao", "tarifaco", "exterior", "preco de transferencia", "mercosul"],
}
TAGS_REFORMA = {"IBS", "CBS", "Imposto Seletivo", "Reforma Tributária"}
TAGS_FISCAL = {"Exclusão da ST", "Substituição Tributária", "NCM", "Prazo", "Vencimento", "Obrigação acessória",
               "Nova obrigação", "NF-e/NFS-e", "Legislação estadual", "ICMS", "ISS", "Benefício fiscal", "IPI",
               "PIS/Cofins", "Nova regra"}

# Palavras que indicam assunto tributário (para filtrar portais e fontes gerais)
PALAVRAS_TRIBUTARIAS = ["tribut", "imposto", "icms", "iss", "ibs", "cbs", "pis", "cofins", "irpj", "csll",
                        "receita federal", "sefaz", "fiscal", "contribuinte", "declaracao", "sped", "efd",
                        "ncm", "funrural", "obrigacao", "aliquota", "nota fiscal", "parcelamento", "simples nacional",
                        "contab", "divida ativa", "transacao", "esocial", "reinf", "dctf", "reforma"]

# ╔══════════════════════════════════════════════════════════════════╗
# ║   FILTRO DE RELEVÂNCIA — só entra o que importa para o Fiscal    ║
# ╚══════════════════════════════════════════════════════════════════╝

# A notícia só entra no painel se tiver pelo menos UM destes assuntos
NUCLEO_FISCAL = {"Exclusão da ST", "Substituição Tributária", "ICMS", "IPI", "IBS", "CBS", "Imposto Seletivo",
                 "Reforma Tributária", "NCM", "Vencimento", "Obrigação acessória", "Nova obrigação", "NF-e/NFS-e",
                 "Legislação estadual", "Benefício fiscal", "PIS/Cofins", "ISS", "FUNRURAL", "Simples Nacional",
                 "Parcelamento/Transação", "Internacional"}

# Assuntos descartados mesmo que falem de tributo (não são rotina do Departamento Fiscal)
DESCARTAR = [r"malha fina", r"restituic\w*", r"lote (residual|de restituic)", r"\birpf\b",
             r"declaracao (anual )?do (imposto de renda|ir)\b", r"imposto de renda (pessoa fisica|2026|2027)",
             r"\binss\b", r"aposentad", r"\bfgts\b", r"carteira assinada", r"trabalho temporario", r"\b6x1\b",
             r"sorteio", r"concurso", r"exame de suficiencia", r"cartilha", r"\bcursos?\b", r"palestra", r"webinar",
             r"semin[aá]rio", r"usdt|bitcoin|cripto", r"\blci\b|\bcdb\b", r"maus-tratos", r"lavagem de dinheiro",
             r"eleic|eleit", r"ultraprocessad", r"leilao", r"\bipva\b", r"\bitcmd\b", r"heranca", r"pix\b",
             r"esocial", r"icms (esportivo|ecologico|cultural|educacional)", r"\bissb\b"]
FONTES_BLOQUEADAS = ["instagram", "facebook", "youtube", "tiktok", "linkedin", "twitter", "x.com", "threads"]

# Peso de cada assunto (vale o maior) — base do impacto
PESO_BASE = {"Exclusão da ST": 4, "Nova obrigação": 3, "Vencimento": 3, "NCM": 3, "IBS": 2, "CBS": 2,
             "Imposto Seletivo": 2, "Reforma Tributária": 2, "Substituição Tributária": 2, "Prazo": 2,
             "ICMS": 1, "IPI": 1, "PIS/Cofins": 1, "ISS": 1, "Obrigação acessória": 1, "NF-e/NFS-e": 1,
             "Legislação estadual": 1, "Benefício fiscal": 1, "FUNRURAL": 1, "Simples Nacional": 1,
             "Parcelamento/Transação": 1, "Internacional": 1}

# EVENTOS: o que transforma uma notícia em algo que pede ação
_VERBO_DEF = r"\b(fix|defin|aprov|calcul|propo|divulg|public|anunci|apresent|homolog|confirm|sancion|vot|estabelec)\w*"
EVENTOS = [
    # (nome/etiqueta, [expressões que precisam aparecer TODAS], pontos)
    ("Alíquota", [r"\b(aliquotas?|redutor)\b", r"\b(cbs|ibs|imposto seletivo|imposto do pecado)\b", _VERBO_DEF], 4),
    ("Alíquota", [r"\b(cbs|ibs)\b[^.]{0,40}\d+[,.]\d+ ?%|\d+[,.]\d+ ?%[^.]{0,40}\b(cbs|ibs)\b"], 4),
    ("Nova regra", [r"\b(publica|aprova|sanciona|institui|edita|regulamenta|atualiza|altera|revoga|prorroga|divulga|"
                    r"lanca|determina|fixa)\w*",
                    r"\b(regulamento|decreto|instrucao normativa|in rfb|resolucao|portaria|ato declaratorio|"
                    r"ato cotepe|nota tecnica|manual|leiautes?|layout|ajuste sinief|convenio|protocolo|"
                    r"lei complementar|plp|medida provisoria|lei)\b"], 3),
    ("Prazo", [r"\b(prazos?|data limite|ultimos? dias?|vencimento)\b",
               r"\b(acaba|termina|encerra|vence|prorrog|adiad|novo prazo|posterg|ate (o dia|amanha|hoje|esta|"
               r"nesta|sexta|segunda|terca|quarta|quinta|\d))"], 3),
    ("Vigência", [r"(entra em vigor|entram em vigor|passa a valer|passam a valer|passa a ser obrigatori|"
                  r"torna obrigatori|a partir de (hoje|amanha|\d{1,2}(/| de )))"], 2),
]
PENALIDADES = [
    # especulação / previsão (ainda não aconteceu)
    (r"\b(deve|devem|pode|podem|podera|poderao|devera|deverao|vai|vao|promete|estuda|discute|debate|cogita|"
     r"nesta semana|esta semana|essa semana|na proxima semana|em breve|preve|pauta|julga)\b", 1),
    # conteúdo explicativo / opinião
    (r"^(o que|entenda|saiba|veja|como|por que|quais|qual)\b|\b(entenda|saiba mais|veja como|dicas?|o que muda|"
     r"o que e|guia|passo a passo|especialistas|opiniao|artigo)\b", 1),
    # decisão judicial isolada
    (r"\b(juiz|juiza|justica|liminar|sentenca|trf|stf|stj|carf|tese)\b", 1),
]
LIMITE_ALTO = 6       # pontos para ALTO impacto
LIMITE_MEDIO = 3      # pontos para MÉDIO impacto
LIMITE_MINIMO = 1     # abaixo disso a notícia nem entra no painel

# Veículos de referência (preferidos para representar uma notícia repetida)
VEICULOS_REFERENCIA = ["valor", "jota", "portal contabeis", "contabeis", "agencia brasil", "agencia senado",
                       "consultor juridico", "conjur", "estadao", "folha", "g1", "o globo", "cnn", "infomoney",
                       "migalhas", "fenacon", "jornal contabil", "exame", "reuters", "poder360"]

# Frase simples "Por que importa" — vale a primeira regra que combinar
POR_QUE_IMPORTA = [
    ("Alíquota", "Define quanto será cobrado do novo tributo. Afeta preço, margem e a simulação de carga dos clientes."),
    ("Exclusão da ST", "Muda quem recolhe o ICMS desses produtos. Revise cadastro de produtos, estoque e preços."),
    ("Nova obrigação", "Surgiu uma entrega nova para o fisco. Verifique quais clientes são obrigados e a partir de quando."),
    ("Vencimento", "A data de pagamento mudou. Ajuste o calendário para evitar multa e juros."),
    ("Prazo", "Há prazo novo ou alterado. Atualize a agenda de obrigações da equipe."),
    ("NCM", "O código do produto (NCM) mudou ou foi ajustado. Código errado gera imposto errado e nota rejeitada."),
    ("Imposto Seletivo", "Pode encarecer produtos específicos a partir de 2027. Veja se algum cliente é afetado."),
    ("IBS", "Faz parte da Reforma Tributária: muda notas fiscais, sistemas e cálculo dos impostos sobre consumo."),
    ("CBS", "Faz parte da Reforma Tributária: a CBS substitui PIS e Cofins a partir de 2027."),
    ("Reforma Tributária", "Novidade da Reforma Tributária. Acompanhe para planejar a adaptação dos clientes."),
    ("Substituição Tributária", "Mexe na substituição tributária do ICMS. Confira produtos e estados envolvidos."),
    ("FUNRURAL", "Afeta produtores rurais e quem compra deles. Confira clientes do agro."),
    ("Parcelamento/Transação", "Oportunidade de regularizar dívidas com condições melhores. Observe o prazo de adesão."),
    ("Benefício fiscal", "Pode reduzir imposto de algum cliente. Vale conferir se ele se enquadra."),
    ("Legislação estadual", "Mudança na lei do estado. Verifique se algum cliente opera ali."),
    ("Obrigação acessória", "Envolve declarações entregues ao fisco. Confira se muda algo na rotina."),
    ("ISS", "Afeta prestadores e tomadores de serviço no município."),
    ("NF-e/NFS-e", "Pode exigir ajuste no sistema emissor de notas fiscais."),
    ("Internacional", "Interessa a clientes que importam, exportam ou têm operações no exterior."),
]


# ╔══════════════════════════════════════════════════════════════════╗
# ║                     DAQUI PARA BAIXO: O ROBÔ                     ║
# ╚══════════════════════════════════════════════════════════════════╝

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s  %(message)s", datefmt="%d/%m/%Y %H:%M:%S",
    handlers=[logging.FileHandler(ARQUIVO_LOG, encoding="utf-8"), logging.StreamHandler(sys.stdout)])
log = logging.getLogger("radar")

SESSAO = requests.Session()
SESSAO.headers.update({"User-Agent": "Mozilla/5.0 (RadarTributario-GrupoDicon/1.0)"})
TIMEOUT = 20
FUSO_BR = timezone(timedelta(hours=-3))


def sem_acento(t):
    t = unicodedata.normalize("NFD", t or "")
    return "".join(c for c in t if unicodedata.category(c) != "Mn").lower()


def limpar_html(t):
    t = re.sub(r"<[^>]+>", " ", t or "")
    t = html.unescape(t)
    return re.sub(r"\s+", " ", t).strip()


def encurtar(t, n=260):
    t = (t or "").strip()
    if len(t) <= n:
        return t
    corte = t[:n].rsplit(" ", 1)[0]
    return corte.rstrip(",;:-") + "…"


def google_news(consulta):
    q = quote_plus(f"{consulta} when:{DIAS_PARA_TRAS + 1}d")
    return f"https://news.google.com/rss/search?q={q}&hl=pt-BR&gl=BR&ceid=BR:pt-419"


def ler_feed(url):
    """Baixa e lê um feed. Devolve lista de itens (ou [] se falhar)."""
    try:
        r = SESSAO.get(url, timeout=TIMEOUT)
        if r.status_code != 200 or not r.content:
            return []
        f = feedparser.parse(r.content)
        return f.entries or []
    except Exception as e:  # noqa: BLE001
        log.info(f"   ! não consegui ler {url[:80]} ({type(e).__name__})")
        return []


def data_do_item(e):
    for campo in ("published_parsed", "updated_parsed"):
        v = e.get(campo)
        if v:
            try:
                return datetime(*v[:6], tzinfo=timezone.utc)
            except Exception:  # noqa: BLE001
                pass
    return datetime.now(timezone.utc)


def item_para_noticia(e, fonte_nome, tipo, veio_do_google):
    titulo = limpar_html(e.get("title", ""))
    fonte_real = fonte_nome
    if veio_do_google:
        # Google Notícias põe " - Nome do site" no fim do título
        src = e.get("source", {}) or {}
        nome_site = src.get("title") if isinstance(src, dict) else None
        if " - " in titulo:
            titulo, sufixo = titulo.rsplit(" - ", 1)
            nome_site = nome_site or sufixo
        if nome_site and fonte_nome.startswith("Busca"):
            fonte_real = nome_site.strip()
        site_url = (src.get("href") if isinstance(src, dict) else "") or ""
    else:
        nome_site, site_url = fonte_nome, e.get("link", "")
    resumo = limpar_html(e.get("summary", "") or e.get("description", ""))
    if veio_do_google or sem_acento(resumo).startswith(sem_acento(titulo)[:40]):
        resumo = ""  # o resumo do Google é só o título repetido
    return {
        "titulo": titulo.strip(),
        "resumo": encurtar(resumo),
        "link": e.get("link", ""),
        "fonte": fonte_real,
        "tipo_fonte": tipo,
        "data": data_do_item(e).isoformat(),
        "_site_url": site_url or "",
        "_site_nome": (nome_site or "").strip(),
    }


def ajustar_origem(n, dominio, nome_oficial, tipo_oficial):
    """Se a notícia veio do site oficial, mantém o nome oficial; se veio de jornal, usa o nome do jornal."""
    dom = dominio.split("/")[0]
    if dom in n.get("_site_url", "") or dom in (n.get("link") or ""):
        n["fonte"], n["tipo_fonte"] = nome_oficial, tipo_oficial
    else:
        n["fonte"] = n.get("_site_nome") or n["fonte"]
        n["tipo_fonte"] = "Portal de notícias"
    return n


def eh_tributario(n):
    t = sem_acento(n["titulo"] + " " + n["resumo"])
    return any(p in t for p in PALAVRAS_TRIBUTARIAS)


def recente(n):
    d = datetime.fromisoformat(n["data"])
    return d >= datetime.now(timezone.utc) - timedelta(days=DIAS_PARA_TRAS)


# --------------------------- COLETA ---------------------------------

def coletar_fonte(f):
    achadas = []
    for url in f["rss"]:
        itens = ler_feed(url)
        if itens:
            achadas += [item_para_noticia(e, f["nome"], f["tipo"], False) for e in itens[:60]]
            break
    # complementa (ou substitui, se o feed falhou) com o Google Notícias
    itens = ler_feed(google_news(f["busca"]))
    achadas += [ajustar_origem(item_para_noticia(e, f["nome"], f["tipo"], True), f["dominio"], f["nome"], f["tipo"])
                for e in itens[:LIMITE_FONTE]]
    achadas = [n for n in achadas if n["titulo"] and recente(n)]
    if f.get("filtrar"):
        achadas = [n for n in achadas if eh_tributario(n)]
    for n in achadas:
        n["_esfera_fonte"] = f.get("esfera")
    return achadas[:LIMITE_FONTE * 2]


def coletar_estado(uf):
    nome, site = SEFAZ[uf]
    foco = uf in ESTADOS_FOCO
    limite = LIMITE_ESTADO_FOCO if foco else LIMITE_ESTADO_COMUM
    consultas = [f'(site:{site} OR "Sefaz {uf}" OR "Sefaz-{uf}" OR "Secretaria da Fazenda" "{nome}") '
                 f'(ICMS OR imposto OR tributo OR decreto)']
    if foco:
        consultas += [
            f'"{nome}" ICMS ("substituição tributária" OR "ICMS-ST")',
            f'"{nome}" ICMS (prazo OR vencimento OR "obrigação acessória" OR prorroga)',
            f'"{nome}" (decreto OR portaria OR convênio) ICMS',
            f'"{nome}" ("reforma tributária" OR IBS) Sefaz',
        ]
    achadas = []
    for url in SEFAZ_RSS_EXTRA.get(uf, []):
        achadas += [item_para_noticia(e, f"SEFAZ-{uf}", "SEFAZ estadual", False) for e in ler_feed(url)[:limite]]
    for c in consultas:
        for e in ler_feed(google_news(c))[:limite]:
            n = item_para_noticia(e, f"SEFAZ-{uf}", "SEFAZ estadual", True)
            # Notícia do site oficial fica como "SEFAZ-UF"; de jornal, com o nome do jornal
            ajustar_origem(n, site, f"SEFAZ-{uf}", "SEFAZ estadual")
            if n["fonte"] == f"SEFAZ-{uf}" and n["tipo_fonte"] == "Portal de notícias":
                n["fonte"] = f"Imprensa ({uf})"
            n["_uf"] = uf
            achadas.append(n)
        time.sleep(0.6)
    achadas = [n for n in achadas if n["titulo"] and recente(n) and eh_tributario(n)]
    return achadas


# Portal de legislação da SEFAZ-SP: dados abertos com todos os atos
# (portarias, decretos, comunicados, respostas à consulta) — não depende de virar notícia.
LEGIS_SP_API = ("https://legislacao.fazenda.sp.gov.br/_api/web/lists/getbytitle('P%C3%A1ginas')/items"
                "?$top=200&$orderby=Created%20desc&$select=Title,Tipo,DataPublicacao,DataAto,FileLeafRef,Ementa")
LEGIS_SP_PAGINA = "https://legislacao.fazenda.sp.gov.br/Paginas/"


def coletar_legislacao_sp():
    try:
        r = SESSAO.get(LEGIS_SP_API, timeout=TIMEOUT, headers={"Accept": "application/json;odata=nometadata"})
        itens = r.json().get("value", []) if r.status_code == 200 else []
    except Exception as e:  # noqa: BLE001
        log.info(f"   ! portal de legislação SP indisponível ({type(e).__name__})")
        return []
    limite = datetime.now(timezone.utc) - timedelta(days=max(DIAS_LEGISLACAO, DIAS_PARA_TRAS))
    achadas = []
    for it in itens:
        tipo = (it.get("Tipo") or "").strip()
        if "Consulta" in tipo and not INCLUIR_RESPOSTAS_CONSULTA:
            continue
        bruto = it.get("DataPublicacao") or it.get("DataAto")
        if not bruto or not it.get("FileLeafRef"):
            continue
        try:
            data = datetime.fromisoformat(bruto.replace("Z", "+00:00"))
        except ValueError:
            continue
        if data < limite:
            continue
        nome = (it.get("Title") or "").strip()
        ementa = limpar_html(it.get("Ementa") or "")
        achadas.append({
            "titulo": f"{nome}: {encurtar(ementa, 150)}" if ementa else nome,
            "resumo": encurtar(ementa, 360) if len(ementa) > 150 else "",
            "link": LEGIS_SP_PAGINA + it["FileLeafRef"],
            "fonte": "SEFAZ-SP · Legislação",
            "tipo_fonte": "SEFAZ estadual",
            "data": data.isoformat(),
            "_uf": "SP",
            "_ato": tipo,
        })
    return achadas


def carregar_destaques():
    """Lê o destaques.json: atos importantes fixados pela equipe, com data de vigência."""
    if not ARQUIVO_DESTAQUES.exists():
        return []
    try:
        lista = json.loads(ARQUIVO_DESTAQUES.read_text(encoding="utf-8")).get("destaques", [])
    except Exception as e:  # noqa: BLE001
        log.info(f"destaques.json com erro de digitação, ignorado ({e}). Confira vírgulas e aspas.")
        return []
    hoje = datetime.now(FUSO_BR).date().isoformat()
    saida = []
    for d in lista:
        if not d.get("titulo"):
            continue
        vig = d.get("vigencia") or d.get("publicado_em") or hoje
        ate = d.get("fixar_ate") or (datetime.fromisoformat(vig) + timedelta(days=90)).date().isoformat()
        if ate < hoje:
            continue  # já passou do prazo de ficar fixado
        n = {"titulo": d["titulo"], "resumo": d.get("resumo", ""), "link": d.get("link", ""),
             "fonte": d.get("fonte", "Equipe Dicon"), "tipo_fonte": d.get("tipo_fonte", "SEFAZ estadual"),
             "data": f"{d.get('publicado_em') or vig}T12:00:00+00:00"}
        if d.get("uf"):
            n["_uf"] = d["uf"]
        base = dict(n)
        n = classificar(n) or {**base, "esfera": d.get("esfera", "Estadual"), "uf": d.get("uf", ""), "tags": [],
                                "porque": "", "reforma": False, "fiscal": True, "internacional": False,
                                "impacto": "alto", "outras_fontes": []}
        for campo in ("esfera", "impacto", "porque"):
            if d.get(campo):
                n[campo] = d[campo]
        if d.get("tags"):
            n["tags"] = d["tags"]
            n["reforma"] = bool(set(d["tags"]) & TAGS_REFORMA) or n["reforma"]
            n["fiscal"] = bool(set(d["tags"]) & TAGS_FISCAL) or n["fiscal"]
        n.update({"id": "fx-" + chave(n), "fixo": True, "vigencia": vig})
        saida.append(n)
    return saida


def coletar_temas():
    achadas = []
    for tag, consulta in BUSCAS_TEMAS:
        for e in ler_feed(google_news(consulta))[:LIMITE_FONTE]:
            n = item_para_noticia(e, "Busca temática", "Portal de notícias", True)
            n["_tag_busca"] = tag
            achadas.append(n)
        time.sleep(0.6)
    return [n for n in achadas if n["titulo"] and recente(n) and eh_tributario(n)]


# ------------------------- CLASSIFICAÇÃO ----------------------------

NOMES_UF = {sem_acento(v[0]): k for k, v in SEFAZ.items()}
# "para" sem acento confunde com a preposição: só vale com contexto
NOMES_UF.pop("para", None)
NOMES_UF.update({"estado do para": "PA", "governo do para": "PA", "sefa-pa": "PA", "sefa pa": "PA", "no para": "PA"})
CAPITAIS = {"rio branco": "AC", "maceio": "AL", "macapa": "AP", "manaus": "AM", "salvador": "BA", "fortaleza": "CE",
            "brasilia": "DF", "vitoria": "ES", "goiania": "GO", "sao luis": "MA", "cuiaba": "MT",
            "campo grande": "MS", "belo horizonte": "MG", "belem": "PA", "joao pessoa": "PB", "curitiba": "PR",
            "recife": "PE", "teresina": "PI", "natal": "RN", "porto alegre": "RS", "porto velho": "RO",
            "boa vista": "RR", "florianopolis": "SC", "aracaju": "SE", "palmas": "TO", "taubate": "SP",
            "campinas": "SP", "guarulhos": "SP", "niteroi": "RJ", "uberlandia": "MG", "contagem": "MG",
            "feira de santana": "BA", "joinville": "SC", "mossoro": "RN", "caruaru": "PE"}
# Verbo de saída + "substituição tributária" na mesma frase = Exclusão da ST
RE_EXCLUSAO_ST = re.compile(r"\b(exclu\w*|retir\w*|revog\w*|deixa\w* de|fim d[aoe]|saida d\w*|remov\w*|tira\w*)\b"
                            r"[^.]{0,80}\b(substituicao tributaria|icms[- /]?st|regime de st|da st)\b")
TIPO_OFICIAL = {"Órgão federal", "Legislativo", "SEFAZ estadual"}


def detectar_uf(texto):
    for nome, uf in sorted({**CAPITAIS, **NOMES_UF}.items(), key=lambda x: -len(x[0])):
        if re.search(rf"\b{re.escape(nome)}\b", texto):
            return uf
    m = re.search(r"sefaz[\s\-/]?(" + "|".join(SEFAZ.keys()).lower() + r")\b", texto)
    return m.group(1).upper() if m else ""


def eventos_de(texto):
    achados, pontos = [], 0
    for nome, exprs, pts in EVENTOS:
        if nome in achados:
            continue
        if all(re.search(e, texto) for e in exprs):
            achados.append(nome)
            pontos += pts
    return achados, pontos


def classificar(n):
    """Classifica a notícia. Devolve None quando ela não interessa ao Departamento Fiscal."""
    titulo_sa = sem_acento(n["titulo"])
    texto = " " + sem_acento(n["titulo"] + " " + n["resumo"]) + " "

    # 1) Descarte: fonte de rede social ou assunto fora do Fiscal
    if any(b in sem_acento(n.get("fonte", "")) for b in FONTES_BLOQUEADAS):
        return None
    if any(re.search(p, texto) for p in DESCARTAR):
        return None

    tags = [t for t, palavras in TAGS.items() if any(p in texto for p in palavras)]
    if "Exclusão da ST" not in tags and RE_EXCLUSAO_ST.search(texto):
        tags.append("Exclusão da ST")
    if n.get("_tag_busca") in ("FUNRURAL", "Imposto Seletivo") and n["_tag_busca"] not in tags:
        tags.append(n["_tag_busca"])
    if "Exclusão da ST" in tags and "Substituição Tributária" in tags:
        tags.remove("Substituição Tributária")
    for fraco in ("Agro", "IRPJ/CSLL"):
        if fraco in tags and len(tags) > 2:
            tags.remove(fraco)

    oficial = n["tipo_fonte"] in TIPO_OFICIAL
    nucleo = set(tags) & NUCLEO_FISCAL
    if "Parcelamento/Transação" in nucleo and not oficial and len(nucleo) == 1:
        nucleo = set()          # parcelamento só vale vindo do órgão oficial
    if not nucleo:
        return None

    eventos, pts_evento = eventos_de(texto)
    if "Consulta" in (n.get("_ato") or "") and "Nova regra" in eventos:
        eventos.remove("Nova regra")      # Resposta à Consulta interpreta a regra, não cria regra nova
        pts_evento -= 3
    # Reforma "genérica" (opinião, política, previsão) sem nenhum fato concreto: fora
    if nucleo <= {"Reforma Tributária"} and not eventos:
        return None

    # Notícia achada na busca de um estado, mas que não fala dele (ex.: tema nacional): não prende ao estado
    if n.get("_uf") and n["tipo_fonte"] != "SEFAZ estadual" and "sefaz" not in texto \
            and detectar_uf(texto) != n["_uf"]:
        n.pop("_uf")
    uf = n.get("_uf") or detectar_uf(texto)

    # Esfera
    if "Internacional" in tags and not uf:
        esfera = "Internacional"
    elif "ISS" in tags or "prefeitura" in texto or "municip" in texto:
        esfera = "Municipal"
    elif n.get("_uf") or n["tipo_fonte"] == "SEFAZ estadual":
        esfera = "Estadual"
    elif n.get("_esfera_fonte"):
        esfera = n["_esfera_fonte"]
    elif uf and ("ICMS" in tags or "sefaz" in texto or "Legislação estadual" in tags):
        esfera = "Estadual"
    else:
        esfera = "Federal"
    if esfera == "Federal" and "Legislação estadual" in tags and not uf:
        tags.remove("Legislação estadual")

    # Pontuação
    pontos = max(PESO_BASE.get(t, 0) for t in tags if t in PESO_BASE) if any(t in PESO_BASE for t in tags) else 0
    if len(nucleo) >= 3:
        pontos += 1
    pontos += pts_evento
    if uf in ESTADOS_FOCO:
        pontos += 2
    if oficial:
        pontos += 1
    for expr, menos in PENALIDADES:
        if re.search(expr, titulo_sa):
            pontos -= menos
    if pontos < LIMITE_MINIMO:
        return None

    for ev in eventos:
        if ev in ("Alíquota", "Nova regra") and ev not in tags:
            tags.insert(0, ev)
    ordem = list(TAGS.keys())
    tags.sort(key=lambda t: (t not in ("Alíquota", "Nova regra"), -PESO_BASE.get(t, 0),
                             ordem.index(t) if t in ordem else 0))
    porque = next((frase for tag, frase in POR_QUE_IMPORTA if tag in tags), "")

    n.update({
        "esfera": esfera, "uf": uf if esfera in ("Estadual", "Municipal") or uf else "",
        "tags": tags[:6], "porque": porque, "pontos": pontos,
        "reforma": bool(set(tags) & TAGS_REFORMA), "fiscal": bool(set(tags) & TAGS_FISCAL),
        "internacional": "Internacional" in tags,
    })
    n["impacto"] = nivel(pontos)
    if "Consulta" in (n.get("_ato") or ""):
        n["tags"] = (["Resposta à Consulta"] + n["tags"])[:6]
    elif n.get("_ato"):
        n["ato"] = n["_ato"]
    outras = n.get("_outras") or n.get("outras_fontes") or []
    for k in [k for k in n if k.startswith("_")]:
        n.pop(k)
    n["outras_fontes"] = outras
    return n


def nivel(pontos):
    return "alto" if pontos >= LIMITE_ALTO else "medio" if pontos >= LIMITE_MEDIO else "baixo"


# ---------- Agrupar a mesma notícia publicada por vários veículos ----------
PALAVRAS_VAZIAS = set("para pela pelo pelos pelas entre como mais menos apos ainda sera serao esta este essa esse "
                      "isso desde pode podem deve devem nova novo novas novos governo brasil diz dizem afirma veja "
                      "saiba entenda sobre quando onde qual quais todos todas cada pois porque".split())


def assinatura(n):
    t = sem_acento(n["titulo"])
    nums = {re.sub(r"^(\d+)[,.](\d).*$", r"\1,\2", x) for x in re.findall(r"\d+[,.]\d+", t)}
    palavras = {w for w in re.findall(r"[a-z]{4,}", t) if w not in PALAVRAS_VAZIAS}
    return palavras, nums


def prioridade_fonte(n):
    if n["tipo_fonte"] in TIPO_OFICIAL:
        return 0
    f = sem_acento(n["fonte"])
    return 1 if any(v in f for v in VEICULOS_REFERENCIA) else 2


def agrupar(lista):
    """Junta notícias sobre o mesmo fato num só cartão (com a lista das outras fontes)."""
    lista = sorted(lista, key=lambda n: (prioridade_fonte(n), not n.get("resumo"), n["data"]))
    grupos = []
    for n in lista:
        pal, nums = assinatura(n)
        dn = datetime.fromisoformat(n["data"])
        alvo = None
        for g in grupos:
            if abs((datetime.fromisoformat(g["rep"]["data"]) - dn).days) > 4:
                continue
            gp, gn = g["sig"]
            uniao = len(pal | gp) or 1
            jac = len(pal & gp) / uniao
            tags_comuns = set(n["tags"]) & set(g["rep"]["tags"]) & (NUCLEO_FISCAL | {"Alíquota"})
            mesma_aliquota = ("Alíquota" in n["tags"] and "Alíquota" in g["rep"]["tags"]
                              and set(n["tags"]) & set(g["rep"]["tags"]) & {"CBS", "IBS", "Imposto Seletivo"}
                              and abs((datetime.fromisoformat(g["rep"]["data"]) - dn).days) <= 2)
            if (jac >= 0.4 or (nums & gn and tags_comuns and len(pal & gp) >= 1)
                    or (jac >= 0.25 and len(tags_comuns) >= 2) or mesma_aliquota):
                alvo = g
                break
        if alvo:
            alvo["membros"].append(n)
        else:
            grupos.append({"rep": n, "sig": (pal, nums), "membros": [n]})

    def nota_rep(m):
        t = sem_acento(m["titulo"])
        midia = bool(re.match(r"(audio|video|podcast|ao vivo)\b", t))
        tem_numero = bool(re.search(r"\d+[,.]\d+ ?%", t))
        return (midia, prioridade_fonte(m), -m.get("pontos", 0), not tem_numero, not m.get("resumo"))

    saida = []
    for g in grupos:
        g["membros"].sort(key=nota_rep)
        rep = dict(g["membros"][0])
        fontes, vistos = [], {sem_acento(rep["fonte"])}
        for m in g["membros"][1:] + [o for m in g["membros"] for o in m.get("outras_fontes", [])]:
            chave_f = sem_acento(m["fonte"])
            if chave_f in vistos or not m.get("link"):
                continue
            vistos.add(chave_f)
            fontes.append({"fonte": m["fonte"], "link": m["link"]})
        rep["outras_fontes"] = fontes[:12]
        rep["n_fontes"] = 1 + len(fontes)
        rep["data"] = max(m["data"] for m in g["membros"])
        pontos = max(m.get("pontos", 0) for m in g["membros"])
        pontos += 2 if rep["n_fontes"] >= 6 else 1 if rep["n_fontes"] >= 3 else 0
        tags = list(rep["tags"])
        for m in g["membros"]:
            for t in m["tags"]:
                if t in ("Alíquota", "Nova regra") and t not in tags:
                    tags.insert(0, t)
        rep["tags"] = tags[:6]
        if "Alíquota" in tags:
            rep["porque"] = next(f for t, f in POR_QUE_IMPORTA if t == "Alíquota")
        rep["pontos"], rep["impacto"] = pontos, nivel(pontos)
        saida.append(rep)
    return saida


def cru(n):
    """Reconstrói a notícia guardada no histórico para ser reclassificada com as regras atuais."""
    r = {k: n.get(k, "") for k in ("titulo", "resumo", "link", "fonte", "tipo_fonte", "data")}
    if n.get("esfera") == "Estadual" and n.get("uf"):
        r["_uf"] = n["uf"]
    if "Resposta à Consulta" in n.get("tags", []):
        r["_ato"] = "Respostas de Consultas"
    elif n.get("ato"):
        r["_ato"] = n["ato"]
    if n.get("outras_fontes"):
        r["_outras"] = n["outras_fontes"]
    return r


def chave(n):
    t = re.sub(r"[^a-z0-9 ]", "", sem_acento(n["titulo"]))
    t = re.sub(r"\s+", " ", t).strip()[:90]
    return hashlib.sha1(t.encode()).hexdigest()[:12]


PRIORIDADE_TIPO = {"Órgão federal": 0, "SEFAZ estadual": 0, "Legislativo": 1, "Entidade contábil": 2,
                   "Portal de notícias": 3}


def deduplicar(lista):
    unicos = {}
    for n in lista:
        n["id"] = chave(n)
        atual = unicos.get(n["id"])
        if not atual or PRIORIDADE_TIPO.get(n["tipo_fonte"], 9) < PRIORIDADE_TIPO.get(atual["tipo_fonte"], 9):
            if atual and not n.get("resumo"):
                n["resumo"] = atual.get("resumo", "")
            unicos[n["id"]] = n
    return list(unicos.values())


# ------------------- RESUMO SIMPLES COM IA (opcional) ---------------

def simplificar_com_ia(noticias):
    chave_api = os.getenv("ANTHROPIC_API_KEY")
    if not chave_api:
        return
    alvos = [n for n in noticias if n["impacto"] in ("alto", "medio") and not n.get("_ia")][:IA_MAX_RESUMOS]
    if not alvos:
        return
    log.info(f"Reescrevendo {len(alvos)} resumo(s) em linguagem simples com IA…")
    for n in alvos:
        pedido = ("Você escreve para uma equipe de escritório contábil. Em no máximo 2 frases curtas, "
                  "em português simples e sem jargão, explique o que esta notícia diz. Não invente dados "
                  "que não estejam no texto. Responda só com o resumo.\n\n"
                  f"Título: {n['titulo']}\nTrecho: {n['resumo']}\nFonte: {n['fonte']}")
        try:
            r = requests.post("https://api.anthropic.com/v1/messages", timeout=40, headers={
                "x-api-key": chave_api, "anthropic-version": "2023-06-01", "content-type": "application/json"},
                json={"model": IA_MODELO, "max_tokens": 200, "messages": [{"role": "user", "content": pedido}]})
            if r.status_code == 200:
                texto = "".join(b.get("text", "") for b in r.json().get("content", []))
                if texto.strip():
                    n["resumo"] = encurtar(texto.strip(), 320)
                    n["_ia"] = True
            else:
                log.info(f"   IA indisponível agora (código {r.status_code}). Sigo sem ela.")
                return
        except Exception as e:  # noqa: BLE001
            log.info(f"   IA falhou ({type(e).__name__}). Sigo sem ela.")
            return


# ------------------------ HISTÓRICO E PAINEL ------------------------

def carregar_historico():
    if ARQUIVO_HISTORICO.exists():
        try:
            todas = json.loads(ARQUIVO_HISTORICO.read_text(encoding="utf-8")).get("noticias", [])
            return [n for n in todas if not n.get("fixo")]
        except Exception:  # noqa: BLE001
            log.info("Histórico ilegível; começando do zero.")
    return []


def juntar(historico, novas):
    por_id = {n["id"]: n for n in historico}
    for n in novas:
        if n["id"] in por_id:
            # mantém o resumo de IA já feito
            if por_id[n["id"]].get("_ia"):
                n["resumo"], n["_ia"] = por_id[n["id"]]["resumo"], True
        por_id[n["id"]] = {**por_id.get(n["id"], {}), **n}
    limite = datetime.now(timezone.utc) - timedelta(days=DIAS_NO_PAINEL)
    lista = [n for n in por_id.values() if datetime.fromisoformat(n["data"]) >= limite]
    lista.sort(key=lambda n: n["data"], reverse=True)
    return lista[:MAX_NO_PAINEL]


def atualizar_painel(noticias, n_fontes):
    dados = {"meta": {"atualizado_em": datetime.now(timezone.utc).isoformat(), "demo": False,
                      "fontes_consultadas": n_fontes, "versao": 1},
             "noticias": noticias}
    js = json.dumps(dados, ensure_ascii=False, indent=0).replace("</", "<\\/")
    bloco = f'<!--DADOS_INICIO-->\n<script id="radar-dados">\nwindow.RADAR_DADOS = {js};\n</script>\n<!--DADOS_FIM-->'
    painel = ARQUIVO_PAINEL.read_text(encoding="utf-8")
    novo, qtd = re.subn(r"<!--DADOS_INICIO-->.*?<!--DADOS_FIM-->", lambda m: bloco, painel, flags=re.S)
    if qtd != 1:
        raise RuntimeError("Não achei as marcações <!--DADOS_INICIO--> / <!--DADOS_FIM--> no index.html")
    ARQUIVO_PAINEL.write_text(novo, encoding="utf-8")
    ARQUIVO_HISTORICO.write_text(json.dumps({"atualizado_em": dados["meta"]["atualizado_em"],
                                             "noticias": noticias}, ensure_ascii=False, indent=1),
                                 encoding="utf-8")


# ----------------------------- E-MAIL -------------------------------

def montar_email(noticias):
    hoje = datetime.now(FUSO_BR).date()
    do_dia = [n for n in noticias if datetime.fromisoformat(n["data"]).astimezone(FUSO_BR).date() >= hoje - timedelta(days=1)]
    ordem = {"alto": 0, "medio": 1, "baixo": 2}
    do_dia.sort(key=lambda n: (ordem[n["impacto"]], n["data"]))
    cores = {"alto": "#E2335A", "medio": "#E69A1E", "baixo": "#1FAE80"}
    nomes = {"alto": "ALTO", "medio": "MÉDIO", "baixo": "BAIXO"}
    linhas = "".join(
        f'<tr><td style="padding:10px 0;border-bottom:1px solid #E6E9F6">'
        f'<span style="background:{cores[n["impacto"]]};color:#fff;font-size:10px;font-weight:700;padding:2px 7px;border-radius:4px">{nomes[n["impacto"]]}</span> '
        f'<span style="color:#6A719E;font-size:12px">{html.escape(n["esfera"])}{" · " + n["uf"] if n.get("uf") else ""} · {html.escape(n["fonte"])}</span><br>'
        f'<a href="{html.escape(n["link"])}" style="color:#121854;font-weight:700;text-decoration:none;font-size:14px">{html.escape(n["titulo"])}</a><br>'
        f'<span style="color:#4A5290;font-size:13px">{html.escape(n.get("porque") or n.get("resumo", ""))}</span></td></tr>'
        for n in do_dia[:30])
    altos = sum(1 for n in do_dia if n["impacto"] == "alto")
    botao = (f'<p style="text-align:center;margin:22px 0"><a href="{LINK_DO_PAINEL}" style="background:#2737CF;color:#fff;'
             f'padding:12px 22px;border-radius:8px;text-decoration:none;font-weight:700">Abrir o painel completo</a></p>'
             if LINK_DO_PAINEL else "")
    corpo = f"""<div style="font-family:Arial,sans-serif;max-width:680px;margin:auto;background:#FCFCFC">
<div style="background:#121854;color:#fff;padding:22px 26px;border-radius:12px 12px 0 0">
<div style="font-size:12px;letter-spacing:2px;color:#AEB6EE">GRUPO DICON · DEPARTAMENTO FISCAL</div>
<div style="font-size:22px;font-weight:700;margin-top:4px">Boletim Tributário — {hoje.strftime('%d/%m/%Y')}</div>
<div style="font-size:13px;color:#C9CFFF;margin-top:4px">{len(do_dia)} notícia(s) · {altos} de alto impacto</div></div>
<div style="padding:8px 26px 20px;border:1px solid #E6E9F6;border-top:0;border-radius:0 0 12px 12px">
<table width="100%" cellspacing="0" cellpadding="0">{linhas or '<tr><td style="padding:16px 0">Nenhuma notícia nova hoje.</td></tr>'}</table>
{botao}<p style="font-size:11px;color:#8A90B8">Resumos automáticos — confira sempre a fonte oficial antes de aplicar.</p></div></div>"""
    return f"Boletim Tributário Dicon {hoje.strftime('%d/%m')} — {altos} alerta(s) de alto impacto", corpo


def enviar_email(noticias):
    if not EMAIL_ATIVO:
        return
    if not EMAIL_SENHA or "@" not in EMAIL_REMETENTE or not EMAIL_DESTINOS:
        log.info("E-mail ativado, mas falta remetente, senha ou destinatários. Pulando envio.")
        return
    assunto, corpo = montar_email(noticias)
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = assunto, EMAIL_REMETENTE, ", ".join(EMAIL_DESTINOS)
    msg.attach(MIMEText(corpo, "html", "utf-8"))
    try:
        with smtplib.SMTP_SSL(EMAIL_SERVIDOR, EMAIL_PORTA, context=ssl.create_default_context(), timeout=30) as s:
            s.login(EMAIL_REMETENTE, EMAIL_SENHA)
            s.sendmail(EMAIL_REMETENTE, EMAIL_DESTINOS, msg.as_string())
        log.info(f"Boletim enviado por e-mail para {len(EMAIL_DESTINOS)} pessoa(s).")
    except Exception as e:  # noqa: BLE001
        log.info(f"Não consegui enviar o e-mail: {e}")


# ------------------------- PUBLICAR NO GITHUB -----------------------

def publicar_github():
    if not PUBLICAR_GITHUB:
        return
    if not GITHUB_TOKEN or "/" not in GITHUB_REPOSITORIO:
        log.info("Publicação ativada, mas falta o token ou o nome do repositório. Pulando.")
        return
    api = f"https://api.github.com/repos/{GITHUB_REPOSITORIO}/contents/"
    cab = {"Authorization": f"Bearer {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    for arq in ["index.html", "noticias.json", "destaques.json", "logo.png", "logo-icone.png"]:
        caminho = PASTA / arq
        if not caminho.exists():
            continue
        try:
            atual = requests.get(api + arq, headers=cab, timeout=TIMEOUT)
            sha = atual.json().get("sha") if atual.status_code == 200 else None
            if sha and arq.startswith("logo"):
                continue  # logo já está lá
            corpo = {"message": f"Radar atualizado {datetime.now(FUSO_BR):%d/%m/%Y %H:%M}",
                     "content": base64.b64encode(caminho.read_bytes()).decode()}
            if sha:
                corpo["sha"] = sha
            r = requests.put(api + arq, headers=cab, json=corpo, timeout=60)
            log.info(f"   site: {arq} {'publicado' if r.status_code in (200, 201) else 'falhou (' + str(r.status_code) + ')'}")
        except Exception as e:  # noqa: BLE001
            log.info(f"   site: erro ao publicar {arq}: {e}")


# ------------------------------ EXECUÇÃO ----------------------------

def executar(teste=False, sem_email=False):
    inicio = time.time()
    log.info("=" * 60)
    log.info("RADAR TRIBUTÁRIO — iniciando busca de notícias")
    global DIAS_PARA_TRAS
    historico = carregar_historico()
    if not historico:
        DIAS_PARA_TRAS = max(DIAS_PARA_TRAS, DIAS_PRIMEIRA_EXECUCAO)
        log.info(f"Primeira execução: buscando os últimos {DIAS_PARA_TRAS} dias.")
    coletadas, n_fontes = [], 0

    legis = coletar_legislacao_sp()
    n_fontes += 1
    log.info(f" {'SEFAZ-SP · Legislação':<24} {len(legis):>3} ato(s)")
    coletadas += legis

    for f in FONTES:
        itens = coletar_fonte(f)
        n_fontes += 1
        log.info(f" {f['nome']:<24} {len(itens):>3} notícia(s)")
        coletadas += itens

    temas = coletar_temas()
    log.info(f" {'Buscas por assunto':<24} {len(temas):>3} notícia(s)")
    coletadas += temas

    ordem_ufs = ESTADOS_FOCO + [u for u in SEFAZ if u not in ESTADOS_FOCO]
    for uf in ordem_ufs:
        itens = coletar_estado(uf)
        n_fontes += 1
        log.info(f" SEFAZ-{uf}{' ★' if uf in ESTADOS_FOCO else '  '}{'':<15} {len(itens):>3} notícia(s)")
        coletadas += itens

    brutas = len(coletadas)
    novas = deduplicar([c for c in (classificar(n) for n in coletadas) if c])
    log.info(f"Coletadas {brutas}; relevantes para o Fiscal: {len(novas)} "
             f"(alto: {sum(n['impacto'] == 'alto' for n in novas)}, "
             f"médio: {sum(n['impacto'] == 'medio' for n in novas)}, "
             f"baixo: {sum(n['impacto'] == 'baixo' for n in novas)})")

    if teste:
        for n in sorted(novas, key=lambda x: x["impacto"])[:40]:
            print(f"[{n['impacto'].upper():5}] {n['esfera']:<13} {n['uf'] or '--'}  {n['titulo'][:90]}  {n['tags']}")
        log.info("Modo teste: o painel NÃO foi alterado.")
        return

    fixos = carregar_destaques()
    log.info(f"Destaques fixados pela equipe: {len(fixos)}")
    if not novas and historico:
        log.info("Nenhuma notícia nova encontrada (internet fora do ar?). Painel mantido como estava.")
    simplificar_com_ia(novas)
    # Reclassifica também o histórico com as regras atuais e junta notícias repetidas
    antigas = deduplicar([c for c in (classificar(cru(n)) for n in historico) if c])
    todas = juntar(antigas, novas)
    todas = agrupar(todas)
    todas.sort(key=lambda n: n["data"], reverse=True)
    log.info(f"Após juntar repetidas: {len(todas)} notícia(s) "
             f"(alto: {sum(n['impacto'] == 'alto' for n in todas)}, "
             f"médio: {sum(n['impacto'] == 'medio' for n in todas)}, "
             f"baixo: {sum(n['impacto'] == 'baixo' for n in todas)})")
    ids_fixos = {f["id"] for f in fixos}
    todas = fixos + [n for n in todas if n["id"] not in ids_fixos]
    atualizar_painel(todas, n_fontes)
    log.info(f"Painel atualizado com {len(todas)} notícia(s) dos últimos {DIAS_NO_PAINEL} dias.")
    if not sem_email:
        enviar_email(todas)
    publicar_github()
    log.info(f"Concluído em {time.time() - inicio:.0f} segundos.")


def agendar():
    try:
        import schedule
    except ImportError:
        print("Falta o componente 'schedule'. Rode o instalar.bat.")
        sys.exit(1)
    log.info(f"Modo automático: vou buscar notícias todo dia às {HORARIO_DIARIO}. "
             "Deixe esta janela aberta (pode minimizar).")
    schedule.every().day.at(HORARIO_DIARIO).do(executar)
    while True:
        schedule.run_pending()
        time.sleep(30)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Radar Tributário — Grupo Dicon")
    p.add_argument("--agendar", action="store_true", help="fica ligado e roda todo dia no horário configurado")
    p.add_argument("--teste", action="store_true", help="só mostra o que achou, sem mexer no painel")
    p.add_argument("--sem-email", action="store_true", help="não envia o e-mail nesta execução")
    a = p.parse_args()
    if a.agendar:
        agendar()
    else:
        executar(teste=a.teste, sem_email=a.sem_email)
