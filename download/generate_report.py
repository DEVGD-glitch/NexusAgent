#!/usr/bin/env python3
"""Generate the NexusAgent comprehensive analysis report in PDF."""

import sys, os

PDF_SKILL_DIR = "/home/z/my-project/skills/pdf"
_scripts = os.path.join(PDF_SKILL_DIR, "scripts")
if _scripts not in sys.path:
    sys.path.insert(0, _scripts)

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import inch, cm
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_JUSTIFY
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    PageBreak, KeepTogether, CondPageBreak, HRFlowable
)
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import registerFontFamily

# ── Fonts ──
pdfmetrics.registerFont(TTFont('SarasaMonoSC', '/usr/share/fonts/truetype/chinese/SarasaMonoSC-Regular.ttf'))
pdfmetrics.registerFont(TTFont('SarasaMonoSCBold', '/usr/share/fonts/truetype/chinese/SarasaMonoSC-Bold.ttf'))
pdfmetrics.registerFont(TTFont('DejaVuSans', '/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'))
pdfmetrics.registerFont(TTFont('NotoSerifSC', '/usr/share/fonts/truetype/noto-serif-sc/NotoSerifSC-Regular.ttf'))
pdfmetrics.registerFont(TTFont('NotoSerifSCBold', '/usr/share/fonts/truetype/noto-serif-sc/NotoSerifSC-Bold.ttf'))
pdfmetrics.registerFont(TTFont('WQY', '/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc'))

registerFontFamily('WQY', normal='WQY', bold='WQY')
registerFontFamily('NotoSerifSC', normal='NotoSerifSC', bold='NotoSerifSCBold')
registerFontFamily('SarasaMonoSC', normal='SarasaMonoSC', bold='SarasaMonoSCBold')

from pdf import install_font_fallback
install_font_fallback()

# ── Palette ──
ACCENT       = colors.HexColor('#461fb9')
TEXT_PRIMARY  = colors.HexColor('#212224')
TEXT_MUTED    = colors.HexColor('#757c81')
BG_SURFACE   = colors.HexColor('#dde0e3')
BG_PAGE      = colors.HexColor('#eaedef')
TABLE_HEADER_COLOR = ACCENT
TABLE_HEADER_TEXT  = colors.white
TABLE_ROW_EVEN     = colors.white
TABLE_ROW_ODD      = BG_SURFACE

# ── Page setup ──
PAGE_W, PAGE_H = A4
LEFT_M = 1.8*cm
RIGHT_M = 1.8*cm
TOP_M = 2*cm
BOTTOM_M = 2*cm
CONTENT_W = PAGE_W - LEFT_M - RIGHT_M

# ── Styles ──
styles = getSampleStyleSheet()

h1_style = ParagraphStyle(
    'H1', fontName='WQY', fontSize=20, leading=28,
    textColor=ACCENT, spaceBefore=24, spaceAfter=12,
    wordWrap='CJK'
)
h2_style = ParagraphStyle(
    'H2', fontName='WQY', fontSize=15, leading=22,
    textColor=ACCENT, spaceBefore=18, spaceAfter=8,
    wordWrap='CJK'
)
h3_style = ParagraphStyle(
    'H3', fontName='WQY', fontSize=12, leading=18,
    textColor=TEXT_PRIMARY, spaceBefore=12, spaceAfter=6,
    wordWrap='CJK'
)
body_style = ParagraphStyle(
    'Body', fontName='WQY', fontSize=10.5, leading=18,
    textColor=TEXT_PRIMARY, alignment=TA_LEFT,
    firstLineIndent=21, wordWrap='CJK',
    spaceBefore=2, spaceAfter=4
)
body_no_indent = ParagraphStyle(
    'BodyNoIndent', fontName='WQY', fontSize=10.5, leading=18,
    textColor=TEXT_PRIMARY, alignment=TA_LEFT,
    wordWrap='CJK', spaceBefore=2, spaceAfter=4
)
bullet_style = ParagraphStyle(
    'Bullet', fontName='WQY', fontSize=10, leading=16,
    textColor=TEXT_PRIMARY, alignment=TA_LEFT,
    leftIndent=20, bulletIndent=8, wordWrap='CJK',
    spaceBefore=1, spaceAfter=2
)
header_cell_style = ParagraphStyle(
    'HeaderCell', fontName='WQY', fontSize=9.5, leading=14,
    textColor=TABLE_HEADER_TEXT, alignment=TA_CENTER, wordWrap='CJK'
)
cell_style = ParagraphStyle(
    'Cell', fontName='WQY', fontSize=9, leading=13,
    textColor=TEXT_PRIMARY, alignment=TA_LEFT, wordWrap='CJK'
)
cell_center = ParagraphStyle(
    'CellCenter', fontName='WQY', fontSize=9, leading=13,
    textColor=TEXT_PRIMARY, alignment=TA_CENTER, wordWrap='CJK'
)
caption_style = ParagraphStyle(
    'Caption', fontName='WQY', fontSize=9, leading=13,
    textColor=TEXT_MUTED, alignment=TA_CENTER, wordWrap='CJK',
    spaceBefore=4, spaceAfter=12
)
critical_style = ParagraphStyle(
    'Critical', fontName='WQY', fontSize=10.5, leading=18,
    textColor=colors.HexColor('#c62828'), alignment=TA_LEFT,
    wordWrap='CJK', spaceBefore=2, spaceAfter=4, leftIndent=12
)
warning_style = ParagraphStyle(
    'Warning', fontName='WQY', fontSize=10.5, leading=18,
    textColor=colors.HexColor('#e65100'), alignment=TA_LEFT,
    wordWrap='CJK', spaceBefore=2, spaceAfter=4, leftIndent=12
)
toc_title_style = ParagraphStyle(
    'TocTitle', fontName='WQY', fontSize=20, leading=28,
    textColor=ACCENT, alignment=TA_CENTER, spaceBefore=40, spaceAfter=30
)
toc_h1 = ParagraphStyle('TocH1', fontName='WQY', fontSize=13, leading=22, leftIndent=20, textColor=TEXT_PRIMARY, wordWrap='CJK')
toc_h2 = ParagraphStyle('TocH2', fontName='WQY', fontSize=11, leading=18, leftIndent=44, textColor=TEXT_MUTED, wordWrap='CJK')

# ── Helpers ──
def P(text, style=body_style):
    return Paragraph(text, style)

def H1(text):
    return Paragraph(f'<b>{text}</b>', h1_style)

def H2(text):
    return Paragraph(f'<b>{text}</b>', h2_style)

def H3(text):
    return Paragraph(f'<b>{text}</b>', h3_style)

def bullet(text):
    return Paragraph(f'<bullet>&bull;</bullet> {text}', bullet_style)

def critical(text):
    return Paragraph(f'<b>[CRITIQUE]</b> {text}', critical_style)

def warning(text):
    return Paragraph(f'<b>[AVERTISSEMENT]</b> {text}', warning_style)

def make_table(headers, rows, col_ratios=None):
    """Create a styled table with header and data rows."""
    data = [[Paragraph(f'<b>{h}</b>', header_cell_style) for h in headers]]
    for row in rows:
        data.append([Paragraph(str(c), cell_style) for c in row])
    
    if col_ratios:
        col_widths = [r * CONTENT_W for r in col_ratios]
    else:
        col_widths = None
    
    t = Table(data, colWidths=col_widths, hAlign='CENTER')
    style_cmds = [
        ('BACKGROUND', (0, 0), (-1, 0), TABLE_HEADER_COLOR),
        ('TEXTCOLOR', (0, 0), (-1, 0), TABLE_HEADER_TEXT),
        ('GRID', (0, 0), (-1, -1), 0.5, TEXT_MUTED),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]
    for i in range(1, len(data)):
        bg = TABLE_ROW_EVEN if i % 2 == 1 else TABLE_ROW_ODD
        style_cmds.append(('BACKGROUND', (0, i), (-1, i), bg))
    t.setStyle(TableStyle(style_cmds))
    return t

def hr():
    return HRFlowable(width="100%", thickness=0.5, color=ACCENT, spaceBefore=8, spaceAfter=8)

# ── Document ──
output_path = "/home/z/my-project/download/NexusAgent_Rapport_Analyse.pdf"

doc = SimpleDocTemplate(
    output_path, pagesize=A4,
    leftMargin=LEFT_M, rightMargin=RIGHT_M,
    topMargin=TOP_M, bottomMargin=BOTTOM_M,
    title="NexusAgent - Rapport d'Analyse Complet",
    author="Z.ai",
    subject="Analyse fichier par fichier du projet NexusAgent"
)

story = []

# ══════════════════════════════════════
# PAGE DE TITRE
# ══════════════════════════════════════
story.append(Spacer(1, 100))
story.append(Paragraph('<b>NEXUSAGENT</b>', ParagraphStyle('TitleMain', fontName='WQY', fontSize=36, leading=44, textColor=ACCENT, alignment=TA_CENTER)))
story.append(Spacer(1, 16))
story.append(Paragraph('Rapport d\'Analyse Complet', ParagraphStyle('TitleSub', fontName='WQY', fontSize=22, leading=30, textColor=TEXT_PRIMARY, alignment=TA_CENTER)))
story.append(Spacer(1, 8))
story.append(hr())
story.append(Spacer(1, 8))
story.append(Paragraph('Analyse fichier par fichier (hors tests)', ParagraphStyle('TitleDesc', fontName='WQY', fontSize=13, leading=20, textColor=TEXT_MUTED, alignment=TA_CENTER)))
story.append(Spacer(1, 30))
story.append(Paragraph('Projet : github.com/DEVGD-glitch/NexusAgent', ParagraphStyle('TitleMeta', fontName='WQY', fontSize=11, leading=16, textColor=TEXT_MUTED, alignment=TA_CENTER)))
story.append(Paragraph('Branche : master', ParagraphStyle('TitleMeta2', fontName='WQY', fontSize=11, leading=16, textColor=TEXT_MUTED, alignment=TA_CENTER)))
story.append(Paragraph('Version : 0.1.0', ParagraphStyle('TitleMeta3', fontName='WQY', fontSize=11, leading=16, textColor=TEXT_MUTED, alignment=TA_CENTER)))
story.append(Spacer(1, 30))
story.append(Paragraph('Date : 13 mai 2026', ParagraphStyle('TitleDate', fontName='WQY', fontSize=11, leading=16, textColor=TEXT_MUTED, alignment=TA_CENTER)))
story.append(Paragraph('Genere par Z.ai', ParagraphStyle('TitleAuthor', fontName='WQY', fontSize=11, leading=16, textColor=TEXT_MUTED, alignment=TA_CENTER)))
story.append(PageBreak())

# ══════════════════════════════════════
# TABLE DES MATIERES
# ══════════════════════════════════════
story.append(Paragraph('<b>Table des Matieres</b>', toc_title_style))
story.append(Spacer(1, 12))

toc_entries = [
    (1, "1. Vue d'ensemble du Projet"),
    (2, "1.1 Identite et objectifs"),
    (2, "1.2 Architecture globale"),
    (2, "1.3 Stack technologique"),
    (1, "2. Analyse des Fichiers Racine"),
    (2, "2.1 Configuration et dependances"),
    (2, "2.2 Scripts de lancement"),
    (2, "2.3 Documentation"),
    (1, "3. Module Core (nexus/core/)"),
    (2, "3.1 Configuration et DI"),
    (2, "3.2 Exceptions et messages d'erreur"),
    (2, "3.3 Registre et superviseur"),
    (2, "3.4 A2A, observabilite et telemetrie"),
    (1, "4. Module LLM (nexus/llm/)"),
    (2, "4.1 Routeur LLM"),
    (2, "4.2 Chaine de fallback"),
    (2, "4.3 Fournisseurs LLM"),
    (1, "5. Module Agents (nexus/agents/)"),
    (2, "5.1 Agent de base (BaseAgent)"),
    (2, "5.2 Agents specialises"),
    (2, "5.3 Couche OpenAI Agents"),
    (1, "6. Module Memoire (nexus/memory/)"),
    (2, "6.1 Systeme memoire 5 niveaux"),
    (2, "6.2 Service ChromaDB"),
    (2, "6.3 Orchestrateur et compacteur"),
    (1, "7. Module Securite (nexus/security/)"),
    (2, "7.1 Guardrails et permissions"),
    (2, "7.2 Sandbox et vault"),
    (2, "7.3 Audit et rate limiting"),
    (1, "8. Modules Knowledge et Orchestrator"),
    (2, "8.1 Recherche profonde et graphe de connaissance"),
    (2, "8.2 Moteurs d'orchestration"),
    (2, "8.3 Motifs et cycle de vie des competences"),
    (1, "9. Modules Reasoning, Dev, API, Comms"),
    (2, "9.1 Raisonnement (ReAct, ToT, LATS)"),
    (2, "9.2 Developpement et execution de code"),
    (2, "9.3 Passerelle API"),
    (2, "9.4 Communication et avatar"),
    (1, "10. Modules Computer, Browser, MCP, CLI"),
    (2, "10.1 Automatisation ordinateur"),
    (2, "10.2 Navigateur et MCP"),
    (2, "10.3 CLI et outils MCP"),
    (1, "11. Frontend (nexus-web/)"),
    (1, "12. Synthese des Bugs Critiques"),
    (1, "13. Recommandations Prioritaires"),
]

for level, text in toc_entries:
    s = toc_h1 if level == 1 else toc_h2
    prefix = '<b>' if level == 1 else ''
    suffix = '</b>' if level == 1 else ''
    story.append(Paragraph(f'{prefix}{text}{suffix}', s))

story.append(PageBreak())

# ══════════════════════════════════════
# 1. VUE D'ENSEMBLE
# ══════════════════════════════════════
story.append(H1("1. Vue d'ensemble du Projet"))

story.append(H2("1.1 Identite et objectifs"))
story.append(P("NexusAgent (NEXUS) se presente comme un agent IA souverain, avec pour slogan Zero Cloud, Zero Compromis. Le projet est entierement redige en francais, ce qui constitue une singularite notable pour un projet open-source de cette envergure. L'objectif affirme est de depasser des concurrents comme Hermes Agent, OpenClaw, Space Agent et Bolt.diy, avec un plan ambitieux de 11 phases de developpement dont seule la phase 1 est completee."))
story.append(P("Le projet revendique 30 000+ lignes de code Python, 22 000+ lignes de tests, 110+ fichiers Python repartis en 22 modules, et 8 fournisseurs LLM dont 3 gratuits sans cle API. La version actuelle est 0.1.0, ce qui indique un stade tres precoce malgre l'ambition affichee. Le depot GitHub contient des placeholders YOUR_USERNAME dans les URLs, suggerant que le projet n'est pas encore pret pour une publication publique."))

story.append(H2("1.2 Architecture globale"))
story.append(P("L'architecture de NEXUS s'articule autour de 22 modules organises en couches distinctes. Le module core fournit la configuration, l'injection de dependances, le registre d'agents et la supervision. Le module llm gere le routage multi-fournisseur avec fallback automatique. Le module memory implemente un systeme memoire hierarchique a 5 niveaux (travail, episodique, semantique, procedurial, identite) soutenu par ChromaDB. Le module orchestrator propose 3 moteurs (LangGraph, CrewAI, Google ADK) avec 6 motifs de coordination. Le module security offre 6 couches complementaires (sandbox, audit, guardrails, permissions, rate limiting, vault)."))

story.append(make_table(
    ["Module", "Fichiers", "Lignes", "Role principal"],
    [
        ["core/", "15", "~2500", "Config, DI, registre, exceptions, A2A"],
        ["llm/", "14", "~2800", "Routeur 13 fournisseurs, fallback, circuit breaker"],
        ["agents/", "7", "~3600", "5 agents specialises + couche OpenAI"],
        ["memory/", "9", "~2200", "Memoire 5 niveaux + ChromaDB + orchestrateur"],
        ["security/", "8", "~2400", "Sandbox, guardrails, vault, audit, permissions"],
        ["knowledge/", "6", "~1800", "Recherche, graphe, RAG, watchdog, web search"],
        ["orchestrator/", "7", "~2200", "3 moteurs, 6 motifs, cycle de vie competences"],
        ["reasoning/", "5", "~1200", "ReAct, Tree-of-Thought, LATS"],
        ["dev/", "6", "~1600", "Moteur de code, execution, deploiement, git"],
        ["api/", "3", "~1100", "Passerelle FastAPI, proxy Puter"],
        ["comms/", "10", "~2500", "Telegram, email, voix, avatar VRM"],
        ["computer/", "5", "~1500", "PyAutoGUI, OCR, controle GUI, processus"],
        ["browser/", "3", "~800", "Service Docker, Playwright"],
        ["mcp_server + mcp_tools/", "14", "~1800", "43+ outils MCP, serveur FastMCP"],
        ["cli/", "2", "~600", "Interface Typer + Rich"],
    ],
    col_ratios=[0.18, 0.08, 0.08, 0.66]
))
story.append(Paragraph("Tableau 1 : Vue d'ensemble des modules du projet NEXUS", caption_style))

story.append(H2("1.3 Stack technologique"))
story.append(P("Le backend utilise Python 3.11+ avec FastAPI, Pydantic 2.11+, ChromaDB 1.0+, LangGraph 0.4+, LiteLLM 1.67+ et Typer pour la CLI. Le frontend est construit avec Next.js 16, React 19, shadcn/ui, Zustand et Framer Motion. L'application desktop utilise Tauri v2. L'orchestration Docker comprend 3 services (nexus-core, chromadb, browser-service). Les dependances optionnelles incluent CrewAI, Google ADK, OpenAI Agents SDK, Playwright et AIAvatarKit."))
story.append(critical("Inconsistance majeure : pyproject.toml et requirements.txt definissent des ensembles de dependances et des contraintes de version differents. L'installation via pip install -e . vs pip install -r requirements.txt produit des environnements differents."))

# ══════════════════════════════════════
# 2. FICHIERS RACINE
# ══════════════════════════════════════
story.append(H1("2. Analyse des Fichiers Racine"))

story.append(H2("2.1 Configuration et dependances"))
story.append(P("Le fichier pyproject.toml definit le paquet nexus-agent v0.1.0 avec 23 dependances principales et des groupes optionnels (browser, desktop, avatar, multiagent, dev). On note des redundances : customtkinter, Pillow et httpx apparaissent a la fois dans les dependances principales et les groupes optionnels. Le fichier requirements.txt contient 50+ paquets avec des contraintes de version differrentes de pyproject.toml (par exemple langgraph est 0.4+ dans pyproject.toml mais inférieur a 1.0 dans requirements.txt). Les paquets de test (pytest, pytest-asyncio, pytest-cov) sont dans requirements.txt mais auraient du rester dans le groupe dev uniquement."))

story.append(P("Le fichier .env.example definit la configuration environnementale avec 13 fournisseurs LLM organises en 3 tiers (gratuits, payants, locaux). Le routeur par defaut est Gemini avec une chaine de fallback vers 7 fournisseurs. Cependant, le port par defaut est 8080 dans .env.example alors que les scripts de lancement utilisent 8081 (car le port 8080 est pris par Windows svchost). La cle secrete par defaut 'change-me-to-a-secure-random-string' represente un risque si les utilisateurs ne la modifient pas."))

story.append(H2("2.2 Scripts de lancement"))
story.append(P("start.sh est le script Unix principal : il cree un venv si absent, installe les dependances, verifie Node.js, copie .env.example vers .env si necessaire, lance le backend sur le port 8081 et le frontend sur le port 3000. start_web.sh est une version simplifiee sans verification de dependances. Les deux scripts utilisent des handlers trap pour l'arret propre. Le script run_nexus.py est un point d'entree alternatif qui ajoute la racine du workspace au sys.path et charge le fichier .env via dotenv."))

story.append(warning("Port inconsistent : .env.example definit PORT=8080, mais start.sh et start_web.sh codent en dur le port 8081. Cette incoherence peut causer des erreurs de connexion."))

story.append(H2("2.3 Documentation"))
story.append(P("Le README.md presente le projet de maniere attractive mais contient des placeholders YOUR_USERNAME dans les URLs GitHub, le rendant inutilisable pour le clonage public. Le CHANGELOG.md est severeement obsolete : la version 1.0.0 datee de 2025-01-01 decrit un projet beaucoup plus simple (OpenAI + Anthropic uniquement), sans reflechir les ajouts massifs recents. Le AGENTS.md est le document technique le plus detaille avec 12 points d'entree, l'architecture complete et les conventions de codage, mais il contient un arbre d'architecture duplique par erreur de copier-coller. PLAN.md decrit 11 phases ambitieuses, dont seule la phase 1 est completee."))

# ══════════════════════════════════════
# 3. MODULE CORE
# ══════════════════════════════════════
story.append(H1("3. Module Core (nexus/core/)"))

story.append(H2("3.1 Configuration et DI"))
story.append(P("Le fichier config.py implemente le pattern Settings Object avec pydantic-settings. La classe NexusConfig contient 50+ champs de configuration organises en 13 categories, charges depuis les variables d'environnement et les fichiers .env. La fonction get_settings() utilise lru_cache pour fournir un singleton efficace avec possibilite de rechargement via reload_settings(). La validation de production bloque l'utilisation de la cle secrete par defaut en mode production."))

story.append(critical("Bug : available_providers inclut toujours ollama, pollinations, g4f et deepinfra, meme s'ils ne sont pas joignables. Cela donne une fausse impression de disponibilite et peut fausser le routage LLM."))

story.append(P("Le fichier di.py implemente un conteneur d'injection de dependances minimaliste avec 95 lignes. Le DIContainer utilise des fabriques et des singletons, mais toutes les fabriques deviennent des singletons apres la premiere resolution, sans possibilite d'instances transitoires. Le conteneur n'est pas thread-safe et configure_container() echoue bruyamment si un module est manquant."))

story.append(H2("3.2 Exceptions et messages d'erreur"))
story.append(P("Le fichier exceptions.py definit une hierarchie d'exceptions structuree avec 6 categories principales (Configuration, Memory, LLM, Orchestrator, Security, Browser) et des sous-types specifiques. Chaque exception porte un code, des details contextuels et une methode to_dict() pour la serialisation API. C'est un excellent design qui facilite le debug et la reponse API. Cependant, des categories manquent : KnowledgeError, CommsError, DesktopError et CLIError n'existent pas."))
story.append(P("Le fichier error_messages.py transforme les exceptions techniques en messages conviviaux en francais via ERROR_MAP. Le systeme utilise un fallback a 3 niveaux : correspondance directe, correspondance par motif, message generique. Probleme : ERROR_MAP mute les entrees en place (effet de bord sur un global partage), et plusieurs types d'exceptions ne sont pas mappes."))

story.append(H2("3.3 Registre et superviseur"))
story.append(critical("Bug critique dans registry.py : spawn() cree un AgentInstance mais n'appelle jamais la fabrique pour creer l'agent reel. Les 5 types par defaut sont enregistres avec factory=None. Le registre est un systeme de suivi sans creation effective d'agents."))
story.append(P("Le superviseur (supervisor.py) est un stub : _monitor_loop() est un no-op avec le commentaire Future: Implement actual health checks. Le superviseur enregistre les services mais ne verifie jamais leur sante et ne les redemarre pas."))

story.append(H2("3.4 A2A, observabilite et telemetrie"))
story.append(P("Le module A2A (a2a.py) implemente le protocole Agent-to-Agent avec decouverte via /.well-known/agent.json, delegation de taches avec polling et messagerie inter-agents. Le module d'observabilite (observability.py) fournit du tracing en memoire avec Span et Tracer, mais sans export vers OpenTelemetry ou Langfuse malgre les references dans la configuration. Le module de telemetrie (telemetry.py) offre du crash reporting opt-in avec sanitization PII, mais les rapports ne sont jamais envoyes et restent locaux."))
story.append(warning("Imports circulaires dans a2a.py : TaskDelegate.wait_for_completion() importe A2AProtocol depuis le meme module."))

# ══════════════════════════════════════
# 4. MODULE LLM
# ══════════════════════════════════════
story.append(H1("4. Module LLM (nexus/llm/)"))

story.append(H2("4.1 Routeur LLM"))
story.append(P("Le routeur LLM (router.py, 818 lignes) est le coeur du sous-systeme LLM. Il gere 13 fournisseurs, 2 modes de routage (fournisseur unique avec retry, ou auto-routage par complexite), et une double strategie d'appel (LiteLLM puis fallback HTTP direct). Gemini est specialise avec un appel direct bypassant LiteLLM en raison d'erreurs 500 intermittentes. Le routeur implemente egalement une boucle d'appel d'outils avec max_tool_turns=10."))
story.append(critical("Bug : _call_glm_direct et _call_ollama_direct sont du code mort jamais appele depuis _call_provider. Les methodes existent mais ne sont jamais utilisees."))
story.append(warning("Le streaming est un no-op : _call_provider_streaming delegue au non-streaming et retourne le contenu. Commentaire : For MVP."))

story.append(H2("4.2 Chaine de fallback"))
story.append(P("La chaine de fallback (fallback.py, 520 lignes) ajoute un circuit breaker, un suivi de sante des fournisseurs et des politiques de retry par-dessus le LLMRouter. Apres 3 echecs consecutifs, un fournisseur est marque UNHEALTHY pendant 60 secondes. La latence moyenne est calculee sur les 100 derniers echantillons."))
story.append(warning("FallbackChain cree un nouveau LLMRouter par tentative, ce qui est couteux et empeche le pooling de connexions. La logique _is_provider_available est dupliquee entre FallbackChain et LLMRouter et peut diverger."))

story.append(H2("4.3 Fournisseurs LLM"))
story.append(P("Les 13 fournisseurs sont implementes avec un pattern coherent : catalogue de modeles, dataclass de reponse, methodes complete/stream/stats. Les fournisseurs payants (OpenAI, Anthropic, Gemini, GLM) utilisent LiteLLM puis fallback HTTP direct. Les fournisseurs gratuits (Pollinations, G4F, DeepInfra) utilisent le routeur FreeProviderRouter avec fallback Pollinations vers G4F."))
story.append(critical("Bug dans free_router.py : G4F_MODELS est reference mais jamais importe, causant un NameError a l'execution."))
story.append(critical("Bug : Les fournisseurs gratuits appellent LLMProviderError avec un seul argument string au lieu des keyword args attendus (provider, reason, model). Cela peut echouer a l'execution."))
story.append(P("Le fournisseur Ollama (ollama_provider.py) a une methode is_available() qui retourne toujours True, meme si le serveur Ollama n'est pas en cours d'execution. Le routeur tentera Ollama meme quand il est indisponible, menant a des erreurs de connexion."))

# ══════════════════════════════════════
# 5. MODULE AGENTS
# ══════════════════════════════════════
story.append(H1("5. Module Agents (nexus/agents/)"))

story.append(H2("5.1 Agent de base (BaseAgent)"))
story.append(P("Le BaseAgent (base.py, 966 lignes) est la classe abstraite pour tous les agents NEXUS. Il implemente le cycle Plan-Execute-Reflect avec des services a initialisation paresseuse (llm_router, memory, security, mcp_client). L'agent gere 32 outils MCP via un dictionnaire hardcoded et 6 outils fallback. La methode _call_llm() implemente une boucle d'appel d'outils complete."))
story.append(critical("execute_with_fallback ne creé pas reellement d'agent de fallback : meme si fallback_agent_type est fourni, la methode retourne juste FAILED avec un message de suggestion."))
story.append(warning("La carte des outils MCP est un dictionnaire hardcoded de 32 entrees, fragile et verbeux. Environ 150 lignes de wrappers quasi-identiques. Aucune gestion de la fenetre de contexte : la liste AgentContext.conversation croit sans limite."))

story.append(H2("5.2 Agents specialises"))
story.append(P("Le ResearcherAgent (researcher.py) decompose les questions de recherche, effectue des recherches web et approfondies, puis synthetise avec citations. Le DeveloperAgent (developer.py) propose 3 modeles de plan (standard, debugging, review) selectionnes par mots-cles. L'AnalystAgent (analyst.py) genere et execute du code Python d'analyse. L'OperatorAgent (operator.py, 671 lignes) est le plus complexe avec 5 modeles de plan et un mode ADVISORY qui genere des plans/scripts sans execution automatique d'operations destructrices."))
story.append(warning("Le DeveloperAgent utilise un regex simpliste pour detecter les chemins de fichiers : re.search(r'[\\w/\\-\\.]+\\.\\w+', task) qui matche aussi python3.11 ou e.g."))

story.append(H2("5.3 Couche OpenAI Agents"))
story.append(P("La couche OpenAI Agents (openai_layer.py, 793 lignes) integre l'OpenAI Agents SDK avec handoffs, guardrails et tracing. Si le SDK n'est pas disponible, le systeme bascule vers une execution native NEXUS avec des handoffs simules. Le HandoffRouter utilise un routage par mots-cles, et les guardrails s'integrent avec la couche de securite NEXUS."))
story.append(critical("Bug : _run_native a la configuration de handoff en pass (ligne 638-642). Les handoffs ne fonctionnent jamais en mode natif."))
story.append(warning("Pas de detection de cycles dans la boucle de handoff : si A delegue a B et B delegue a A, la boucle rebondit max_handoffs fois sans progresser."))

# ══════════════════════════════════════
# 6. MODULE MEMOIRE
# ══════════════════════════════════════
story.append(H1("6. Module Memoire (nexus/memory/)"))

story.append(H2("6.1 Systeme memoire 5 niveaux"))
story.append(P("Le systeme memoire implemente 5 niveaux hierarchiques. L1 Working Memory (working.py) gere la fenetre de contexte active avec un budget de 30K tokens, une eviction par priorite et une compression automatique. L2 Episodic Memory (episodic.py) stocke le journal chronologique des experiences. L3 Semantic Memory (semantic.py) gere les faits de connaissance et les chunks RAG. L4 Procedural Memory (procedural.py) cristallise les competences extraites des trajectoires reussies. L5 Identity Memory (identity.py) stocke les profils utilisateur et les preferences."))

story.append(make_table(
    ["Niveau", "Classe", "Namespace", "Role"],
    [
        ["L1", "WorkingMemory", "(en memoire)", "Contexte actif, budget tokens"],
        ["L2", "EpisodicMemory", "episodes", "Journal des experiences"],
        ["L3", "SemanticMemory", "knowledge", "Faits et chunks RAG"],
        ["L4", "ProceduralMemory", "skills", "Competences cristallisees"],
        ["L5", "IdentityMemory", "identity", "Profils et preferences"],
    ],
    col_ratios=[0.08, 0.22, 0.18, 0.52]
))
story.append(Paragraph("Tableau 2 : Systeme memoire a 5 niveaux", caption_style))

story.append(critical("Bug dans working.py : __post_init__ ne declenche jamais le fallback vers les settings car max_tokens=30000 par defaut et la condition est if self.max_tokens <= 0. La condition devrait etre if self.max_tokens is None."))
story.append(critical("Bug dans identity.py : Impossible de definir language_preference='en' sur merge car 'en' est la valeur par defaut et sert de sentinelle. Meme probleme pour communication_style='professional'."))
story.append(warning("Bug dans episodic.py : recall_recent utilise results['documents'][i] (index plat) tandis que recall_similar utilise results['documents'][0][i] (index imbrique), refletant des formats de reponse ChromaDB differents."))

story.append(H2("6.2 Service ChromaDB"))
story.append(P("Le NexusMemoryService (chroma_service.py) fournit le backend vectoriel avec 6 namespaces valides, un cache de client, une injection automatique de metadonnees et une deduplication par hash SHA-256. Le service gere les upsert sur ID existant et utilise un verrou async pour la concurrence."))
story.append(critical("Bug : _cache_lock est cree mais jamais utilise dans _get_cached_client, permettant la creation de clients dupliques."))
story.append(warning("update() avec texte remplace toutes les metadonnees au lieu de les fusionner, ce qui peut perdre des champs comme source et type."))

story.append(H2("6.3 Orchestrateur et compacteur"))
story.append(critical("Bug critique dans orchestrator.py : recall() pour WORKING memory cree un nouveau WorkingMemory vide au lieu d'utiliser self._working_sessions[session_id]. Le rappel ne retourne jamais rien."))
story.append(critical("Bug critique dans orchestrator.py : Le store semantique utilise le namespace 'semantic' mais SemanticMemory utilise 'knowledge'. Les donnees sont orphelines."))
story.append(P("Le MemoryCompactor (compactor.py) offre la compression, la deduplication et la detection de contradictions. Cependant, detect_contradictions est O(n2) avec une limite arbitraire de 200, et la detection est naive (mots de negation + chevauchement de 5+ mots)."))

# ══════════════════════════════════════
# 7. MODULE SECURITE
# ══════════════════════════════════════
story.append(H1("7. Module Securite (nexus/security/)"))

story.append(H2("7.1 Guardrails et permissions"))
story.append(P("Le module de guardrails (guardrails.py) implemente la validation d'entree/sortie avec 4 guardrails : PromptInjectionGuardrail (14 motifs regex), PIIGuardrail (email, telephone, CB, SSN, IP), ContentModerationGuardrail (violence, auto-mutilation, discours de haine), et OutputValidationGuardrail (fuite de cles API). Le GuardrailManager orchestre le pipeline avec redaction cumulative PII."))
story.append(warning("Les motifs d'injection par prompt sont facilement contournables par obfuscation, astuces Unicode ou nouvelles formulations. Les patterns PII sont centes US (pas de numeros internationaux). La redaction d'adresses IP est trop agressive (matche les numeros de version)."))

story.append(P("Le module de permissions (permissions.py) offre 2 modes (AUTO et CONFIRM) avec 9 types d'actions. Le mode AUTO n'approuve que les actions non dangereuses, le mode CONFIRM demande confirmation pour tout. Cependant, PermissionResult est defini mais jamais utilise : le systeme peut demander une permission mais n'a pas de moyen de recevoir la reponse programmatiquement."))

story.append(H2("7.2 Sandbox et vault"))
story.append(P("Le LocalSandbox (sandbox.py) offre l'execution de code isolee avec un blocklist de motifs dangereux, des restrictions d'import et des limites de ressources. Le DockerSandbox ajoute l'isolation complete (pas de reseau, FS en lecture seule, capacites supprimees, utilisateur non-root). Le PerActionSandbox (docker/per_action_sandbox.py) cree des conteneurs ephemeriques par action."))
story.append(warning("Le sandbox local base sur un blocklist est intrinsequement contournable (ex: getattr(__builtins__, '__imp' + 'ort__')('os')). La documentation recommande correctement le DockerSandbox pour la production."))
story.append(warning("Le fichier pepper du vault n'a pas de permissions restreintes sur aucune plateforme. Le vault stocke des donnees dans ~/.nexus/vault qui peut etre sur NFS ou un filesystem partage."))

story.append(H2("7.3 Audit et rate limiting"))
story.append(P("L'AuditLogger (audit.py) fournit un journal d'audit immutable avec rotation quotidienne et requetes. Le RateLimiter (rate_limiter.py) implemente un algorithme de fenetre glissante avec burst allowance et 4 limites preconfigurees."))
story.append(warning("Le RateLimiter utilise threading.Lock qui peut bloquer l'event loop dans un contexte async. La memoire des fenetres croit sans limite."))

# ══════════════════════════════════════
# 8. KNOWLEDGE ET ORCHESTRATOR
# ══════════════════════════════════════
story.append(H1("8. Modules Knowledge et Orchestrator"))

story.append(H2("8.1 Recherche profonde et graphe de connaissance"))
story.append(P("Le DeepResearch (deep_research.py) decompose un sujet en sous-requetes, recherche iterativement dans ChromaDB et le web, puis synthetise un rapport structure. Cependant, _extract_finding ne fait que prefixer le snippet avec le titre au lieu d'utiliser le LLM comme indique dans la docstring. Le KnowledgeGraph (knowledge_graph.py) utilise NetworkX avec double index (_entity_index et _rel_type_index) pour un acces O(1) aux entites."))
story.append(critical("Bug : _rel_type_index n'est pas mis a jour lors de remove_entity() ni reconstruit lors de load(), creant des references pendantes."))
story.append(warning("Le RAG pipeline (rag_pipeline.py) n'utilise jamais le graphe de connaissance malgre la promesse Multi-source retrieval (ChromaDB + Knowledge Graph). Le reranker est juste un sorted() par score, pas un vrai cross-encoder."))

story.append(P("Le WatchdogService (watchdog.py) offre la surveillance RSS, la detection de changements web et les recherches periodiques avec planification cron-like. Le parsing RSS/Atom base sur des regex est fragile et le cron parser est naif. Le MultiSourceWebSearch (web_search.py) agrege les resultats de 4 moteurs (z-ai-sdk, SerpAPI, Brave, DuckDuckGo) avec fallback en chaine."))
story.append(warning("Le scraping DuckDuckGo via regex est extremement brittle et cassera sans avertissement quand DDG change ses classes CSS."))

story.append(H2("8.2 Moteurs d'orchestration"))
story.append(P("Le LangGraph Engine (langgraph_engine.py) est le moteur principal avec un cycle Plan-Execute-Reflect via StateGraph. Cependant, run_nexus_task() retourne via _run_simple_loop, rendant tout le code LangGraph (lignes 557-596) inaccessible. Le commentaire indique Use simple loop for now (LangGraph graph has state update issues). L'integration LangGraph est effectivement desactivee."))
story.append(critical("Bug critique : Le code LangGraph dans run_nexus_task() est du code mort (inaccessible apres return). L'integration LangGraph est desactivee et non testee."))
story.append(critical("Bug : fn_name potentiellement non defini dans executor_node si tool_calls est vide."))
story.append(critical("Bug : _execute_tool_call code en dur http://127.0.0.1:8081 comme URL du backend, sans configuration possible."))

story.append(P("Le CrewAI Engine (crewai_engine.py) integre le framework CrewAI avec 5 templates d'agents (researcher, developer, analyst, writer, manager) et un fallback natif NEXUS. L'ADK Engine (adk_engine.py) integre le Google Agent Development Kit avec gestion de sessions en memoire. Les deux moteurs suivent le pattern try-native-then-fallback."))
story.append(warning("Le fallback CrewAI est purement sequentiel meme si async_execution=True. L'ADK Engine tronque le contexte de session a 2000 caracteres."))

story.append(H2("8.3 Motifs et cycle de vie des competences"))
story.append(P("Le module patterns.py implemente 6 motifs de coordination multi-agent (Supervisor, Pipeline, Parallel, Hierarchical, Mesh, Swarm). Cependant, supervisor_pattern est fonctionnellement identique a parallel_pattern (les deux executent en parallele avec asyncio.gather), et mesh_pattern execute les agents sequentiellement au lieu de les paralleliser dans chaque round."))
story.append(critical("Bug dans skill_lifecycle.py : La validation n'execute pas reellement le code genere. _run_test_case envoie l'input au LLM au lieu de lancer le code. Le code completement casse passe la validation."))
story.append(warning("deploy_skill stocke la competence dans ChromaDB mais ne l'enregistre jamais comme outil MCP."))

# ══════════════════════════════════════
# 9. REASONING, DEV, API, COMMS
# ══════════════════════════════════════
story.append(H1("9. Modules Reasoning, Dev, API, Comms"))

story.append(H2("9.1 Raisonnement (ReAct, ToT, LATS)"))
story.append(P("Le module de raisonnement propose 3 strategies. ReAct (react.py) implemente la boucle Thought-Action-Observation mais n'execute pas reellement les outils malgre le parametre tools accepte. Le selector (selector.py) choisit la strategie par mots-cles avec fallback vers ReAct."))
story.append(critical("Bug dans ReAct : Le parametre tools est accepte mais completement ignore. La boucle n'a aucune capacite d'execution d'outils."))
story.append(P("Tree-of-Thought (tot.py) implemente le beam search sur des pensees candidates avec evaluation LLM. Mais le parsing du score prend le premier chiffre (8.5 devient 8, 10 devient 1). LATS (lats.py) implemente Monte Carlo Tree Search avec UCB1, mais une simulation coute 6-8 appels LLM, et 20 simulations representent 120-160 appels LLM, ce qui est tres couteux."))
story.append(critical("Bug dans LATS : rollout_node peut etre non defini dans la branche else de l'etape de simulation, causant un UnboundLocalError."))

story.append(H2("9.2 Developpement et execution de code"))
story.append(P("Le CodeEngine (code_engine.py) offre la generation, revue et refactoring de code avec support CodeAct (generation-execution-feedback iteratif). La revue combine des patterns statiques (regex pour eval(), exec(), pickle.load(), injection SQL) et une revue semantique LLM. Le CodeExecutor (code_executor.py) supporte 3 backends (local, Docker, remote) avec stripping des cles API dans l'environnement d'execution."))
story.append(warning("CodeAct : La detection de completion est naive : if 'TASK_COMPLETE' in result.stdout or 'done' in result.stdout.lower(). Le mot 'done' dans toute sortie de programme termine prematurement la boucle."))

story.append(H2("9.3 Passerelle API"))
story.append(P("La passerelle API (api/gateway.py, ~1000+ lignes) expose toutes les capacites NEXUS via FastAPI avec CORS, middleware d'authentification et rate limiting. Elle definit 27+ handlers d'outils couvrant la memoire, le graphe de connaissance, le systeme de fichiers, l'execution de code, la recherche web et l'avatar."))
story.append(critical("Bug : _tool_reason_react importe ReactReasoner qui n'existe pas dans react.py (c'est ReActLoop). ImportError a l'execution."))
story.append(critical("Securite : La comparaison de token utilise != au lieu de hmac.compare_digest(), vulnérable aux attaques temporelles."))
story.append(warning("_tool_install_package permet l'installation arbitraire de paquets pip sans allowlist ni verification. Risque de securite majeur."))

story.append(H2("9.4 Communication et avatar"))
story.append(P("Le module comms implemente Telegram (telegram_bot.py), email/calendar via Gmail API (email_calendar.py), et voix via Whisper/TTS OpenAI (voice_io.py). Le sous-module avatar offre un pipeline Speech-to-Speech complet : VAD, STT, LLM, TTS via VOICEVOX, lip sync et rendu VRM Three.js."))
story.append(critical("Bug dans vrm_renderer.py : Le serveur WebSocket n'est jamais demarre. Le rendu VRM est non fonctionnel."))
story.append(warning("VoiceIO : stream_to_file() est synchrone dans une methode async, bloquant l'event loop. Pas de refresh OAuth2 pour les tokens email/calendar."))

# ══════════════════════════════════════
# 10. COMPUTER, BROWSER, MCP, CLI
# ══════════════════════════════════════
story.append(H1("10. Modules Computer, Browser, MCP, CLI"))

story.append(H2("10.1 Automatisation ordinateur"))
story.append(P("Le module computer fournit l'automatisation desktop via PyAutoGUI + Tesseract OCR (computer_use.py), le controle GUI multi-plateforme avec adaptateurs AT-SPI/UIAutomation (gui_control.py), la gestion de processus (process_manager.py) et la comprehension d'ecran par OCR + Vision (screen_understanding.py)."))
story.append(critical("Bug dans screen_understanding.py : b64[:10000] tronque les donnees base64 dans les appels vision, corrompant les images. Le base64 ne doit jamais etre tronque arbitrairement."))
story.append(warning("Duplication massive entre ComputerUse et GUIController : click, double_click, type_text, hotkey, scroll, capture_screen, etc. sont quasi-identiques. tempfile.mktemp() est un risque de securite (race condition)."))

story.append(H2("10.2 Navigateur et MCP"))
story.append(P("Le BrowserService (browser_service.py) est un client HTTP pour un micro-service Docker browser-use, avec fallback vers le scraping basique. PlaywrightExtensions (playwright_ext.py) offre l'automatisation native Playwright avec selecteurs auto-cicatrisants (4 niveaux : CSS, texte, role, texte partiel)."))
story.append(P("Le serveur MCP (mcp_server.py) expose 43+ outils via FastMCP avec 3 ressources et 3 templates de prompt. Cependant, les outils avatar sont importes mais jamais enregistres dans le serveur MCP, et plusieurs outils sont des stubs retournant not_implemented (reason_tot, reason_lats, run_supervisor, run_swarm, web_screenshot)."))

story.append(H2("10.3 CLI et outils MCP"))
story.append(P("La CLI (cli/app.py) utilise Typer + Rich avec les commandes run, chat, status, config, serve, agents, skills, eval, context7 et memory. La commande chat appelle asyncio.run() dans un contexte potentiellement deja en boucle d'evenements, ce qui peut crasher en Python 3.10+."))
story.append(warning("Les outils MCP ont plusieurs problemes : llm_stream ne streame pas reellement, search_files utilise grep -r avec risque d'injection de commande, et install_package permet l'installation arbitraire de paquets."))

# ══════════════════════════════════════
# 11. FRONTEND
# ══════════════════════════════════════
story.append(H1("11. Frontend (nexus-web/)"))
story.append(P("Le frontend est une application Next.js 16 avec React 19, shadcn/ui, Zustand pour l'etat global et Framer Motion pour les animations. L'interface propose 8 panneaux (Agents Wall, Chat, Tasks, Code, Memory, Knowledge, Tools, Settings) accessibles via une barre laterale animee. Le chat-panel supporte le Markdown, la coloration syntaxique, un avatar VRM avec expressions et animation de pensee, et un flux d'activite en temps reel."))
story.append(P("L'API proxy (route.ts) redirige les requetes vers le backend Python a http://127.0.0.1:8081. Le client API (nexus-api.ts) offre des methodes typees pour tous les endpoints backend. Le store Zustand (nexus-store.ts) gere l'etat global avec un journal d'activite limite a 50 entrees."))
story.append(warning("L'URL du backend est code en dur dans route.ts (http://127.0.0.1:8081). Les headers d'authentification ne sont pas transferes. Le texte de l'interface est en francais code en dur sans framework i18n."))

# ══════════════════════════════════════
# 12. SYNTHESE DES BUGS CRITIQUES
# ══════════════════════════════════════
story.append(H1("12. Synthese des Bugs Critiques"))

story.append(P("L'analyse a revele un nombre significatif de bugs critiques qui affectent le fonctionnement du projet. Le tableau suivant resume les bugs les plus importants, classes par severite."))

story.append(make_table(
    ["Severite", "Module", "Bug"],
    [
        ["CRITIQUE", "orchestrator.py", "recall() WORKING cree un WorkingMemory vide"],
        ["CRITIQUE", "orchestrator.py", "Store semantique namespace 'semantic' vs 'knowledge'"],
        ["CRITIQUE", "langgraph_engine.py", "Code LangGraph inaccessible (apres return)"],
        ["CRITIQUE", "langgraph_engine.py", "fn_name potentiellement non defini"],
        ["CRITIQUE", "skill_lifecycle.py", "Validation n'execute pas le code genere"],
        ["CRITIQUE", "free_router.py", "G4F_MODELS reference mais non importe (NameError)"],
        ["CRITIQUE", "registry.py", "spawn() n'invoque jamais la fabrique"],
        ["CRITIQUE", "openai_layer.py", "Handoff natif non configure (pass)"],
        ["CRITIQUE", "react.py", "Parametre tools accepte mais ignore"],
        ["CRITIQUE", "lats.py", "rollout_node potentiellement non defini"],
        ["CRITIQUE", "gateway.py", "Import ReactReasoner inexistant"],
        ["CRITIQUE", "screen_understanding.py", "Troncature base64 b64[:10000] corrompt images"],
        ["CRITIQUE", "vrm_renderer.py", "Serveur WebSocket jamais demarre"],
        ["HAUT", "working.py", "__post_init__ condition jamais declenchee"],
        ["HAUT", "identity.py", "Impossible de definir langue='en' sur merge"],
        ["HAUT", "chroma_service.py", "update() remplace metadonnees au lieu de fusionner"],
        ["HAUT", "knowledge_graph.py", "_rel_type_index non nettoye/mis a jour"],
        ["HAUT", "gateway.py", "Comparaison token avec != au lieu de hmac.compare_digest"],
    ],
    col_ratios=[0.12, 0.24, 0.64]
))
story.append(Paragraph("Tableau 3 : Synthese des bugs critiques et hauts", caption_style))

# ══════════════════════════════════════
# 13. RECOMMANDATIONS
# ══════════════════════════════════════
story.append(H1("13. Recommandations Prioritaires"))

story.append(P("Sur la base de cette analyse approfondie, voici les recommandations classees par ordre de priorite pour ameliorer la qualite et la fiabilite du projet NexusAgent."))

story.append(H2("Priorite 1 - Bugs critiques a corriger"))
story.append(bullet("Corriger le namespace mismatch dans l'orchestrateur memoire ('semantic' vs 'knowledge')"))
story.append(bullet("Corriger le recall() WORKING pour utiliser les sessions existantes au lieu de creer un WorkingMemory vide"))
story.append(bullet("Reactiver ou supprimer le code LangGraph mort dans langgraph_engine.py"))
story.append(bullet("Importer G4F_MODELS dans free_router.py ou remplacer les references"))
story.append(bullet("Corriger l'import ReactReasoner dans gateway.py (c'est ReActLoop)"))
story.append(bullet("Corriger la troncature base64 dans screen_understanding.py"))
story.append(bullet("Faire fonctionner spawn() dans le registre en appelant reellement la fabrique"))

story.append(H2("Priorite 2 - Securite"))
story.append(bullet("Utiliser hmac.compare_digest() pour la comparaison de tokens dans la passerelle API"))
story.append(bullet("Ajouter une allowlist pour install_package ou le desactiver"))
story.append(bullet("Restreindre les permissions du fichier pepper du vault"))
story.append(bullet("Echapper les arguments dans search_files au lieu de les interpoler directement dans grep"))
story.append(bullet("Remplacer tempfile.mktemp() par tempfile.mkstemp() partout"))
story.append(bullet("Ajouter des limites de ressources Docker dans docker-compose.yml"))

story.append(H2("Priorite 3 - Qualite du code"))
story.append(bullet("Harmoniser pyproject.toml et requirements.txt pour des environnements coherents"))
story.append(bullet("Corriger les URLs YOUR_USERNAME dans README.md"))
story.append(bullet("Mettre a jour le CHANGELOG.md pour reflechir l'etat actuel du projet"))
story.append(bullet("Eliminer la duplication entre ComputerUse et GUIController via heritage ou delegation"))
story.append(bullet("Implementer le streaming LLM reel au lieu du stub no-op"))
story.append(bullet("Supprimer le code mort (_call_glm_direct, _call_ollama_direct, _safe_json_parse)"))
story.append(bullet("Creer des singletons pour LLMRouter et NexusMemoryService au lieu de les instancier par appel"))

story.append(H2("Priorite 4 - Ameliorations fonctionnelles"))
story.append(bullet("Implementer l'execution d'outils dans la boucle ReAct"))
story.append(bullet("Ajouter un vrai cross-encoder pour le reranking dans le pipeline RAG"))
story.append(bullet("Integrer le KnowledgeGraph dans le RAG pipeline"))
story.append(bullet("Ajouter la detection de cycles dans la boucle de handoff"))
story.append(bullet("Implementer les stubs (reason_tot, reason_lats, run_supervisor, run_swarm, web_screenshot)"))
story.append(bullet("Ajouter une gestion de fenetre de contexte dans BaseAgent (truncation/summarization)"))
story.append(bullet("Demarrer le serveur WebSocket dans le VRMRenderer"))

story.append(H2("Priorite 5 - Architecture"))
story.append(bullet("Decomposer gateway.py (~1000+ lignes) en routeurs FastAPI separes"))
story.append(bullet("Remplacer le dictionnaire hardcoded de 32 outils MCP par un systeme a auto-decouverte"))
story.append(bullet("Ajouter un nettoyage automatique pour les collections en memoire croissantes (_spans, _instances, _windows, etc.)"))
story.append(bullet("Rendre l'URL du backend configurable dans le frontend (variable d'environnement)"))
story.append(bullet("Ajouter des tests d'integration pour les chemins critiques (LLM routing, memory store/recall, sandbox execution)"))

# ── Build ──
doc.build(story)
print(f"PDF genere avec succes : {output_path}")
