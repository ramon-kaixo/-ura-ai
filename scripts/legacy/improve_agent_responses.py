#!/usr/bin/env python3
"""
Script para mejorar las respuestas procesar() en los agentes de URA
"""

import re
from pathlib import Path

# Respuestas mejoradas por categoría
IMPROVED_RESPONSES = {
    # COCINA
    "cocina_espanola": "Puedo ayudarte con recetas españolas como paella, tortilla, gazpacho, fabada. ¿Qué receta específica buscas?",
    "cocina_navarra": "Especialista en recetas navarras de temporada: menestra, pochas, ajoarriero. ¿Qué producto local tienes?",
    "cocina_italiana": "Puedo generar recetas italianas: pasta, pizza, risotto, lasaña. ¿Qué tipo de cocina italiana prefieres?",
    "cocina_mexicana": "Recetas mexicanas: tacos, burritos, nachos, guacamole. ¿Qué platillo mexicano te interesa?",
    "cocina_peruana": "Especialista en cocina peruana: ceviche, lomo saltado, ají de gallina. ¿Qué receta peruana buscas?",
    "gastronomo_musica": "Puedo crear playlists para acompañar tus cenas y sugerir maridajes vino-música. ¿Qué tipo de comida vas a servir?",
    "orquestador_recetas": "Puedo coordinar múltiples recetas y planificar menús completos. ¿Para cuántas personas y qué ocasión?",
    "media_recetas": "Puedo buscar fotos y vídeos de recetas para inspirarte. ¿Qué plato quieres ver?",
    "vocabulario_gastronomico": "Puedo ayudarte con términos culinarios y descripciones de platos. ¿Qué palabra gastronómica necesitas definir?",
    "vocabulario_bar": "Especialista en vocabulario de hostelería: cocteles, bebidas, bar. ¿Qué término de bar necesitas?",
    "cocina_internacional": "Puedo buscar recetas de cocina internacional y extranjera. ¿De qué país o región?",
    "recetas_con_media": "Puedo buscar recetas con fotos y vídeos. ¿Qué tipo de receta con media necesitas?",
    # CONTABILIDAD/FINANZAS
    "administrativo_contable": "Puedo gestionar facturas con OCR, control de costes y RRHH. ¿Qué tarea administrativa necesitas?",
    "contabilidad": "Puedo ayudarte con IVA, IRPF, asientos contables, nóminas. ¿Qué tema contable necesitas?",
    "facturas": "Puedo emitir, gestionar y cobrar facturas electrónicas. ¿Qué necesitas hacer con facturas?",
    "banco": "Puedo conciliar cuentas, gestionar extractos bancarios y transferencias. ¿Qué operación bancaria necesitas?",
    "vocabulario_financiero": "Puedo definir términos financieros y contables. ¿Qué término financiero necesitas?",
    "contabilidad_agent": "Especialista en PGC, impuestos y autónomos. ¿Qué consulta contable tienes?",
    # MARKETING
    "marketing": "Puedo crear campañas en Instagram, Facebook y métricas. ¿Qué campaña de marketing necesitas?",
    "creativo_marketing": "Puedo diseñar banners, menús digitales y contenido visual. ¿Qué material creativo necesitas?",
    "marketing_navarra": "Marketing estacional de Navarra: San Fermín, productos de temporada. ¿Qué campaña navarra necesitas?",
    "galeria_videos": "Puedo editar vídeos promocionales, reels y contenido visual. ¿Qué tipo de vídeo necesitas?",
    "galeria_fotos": "Puedo gestionar fotos, banners y carteleras. ¿Qué material fotográfico necesitas?",
    "lenguaje_creativo": "Puedo crear copywriting, eslogans y textos publicitarios. ¿Qué contenido creativo necesitas?",
    "marketing_agent": "Puedo crear anuncios, publicaciones y gestionar redes sociales. ¿Qué acción de marketing necesitas?",
    # LEGAL
    "juridico": "Puedo dar asesoría legal, consultar leyes y normativas. ¿Qué consulta jurídica tienes?",
    "policia": "Puedo validar seguridad, checkpoints y autoridad. ¿Qué necesito verificar?",
    "vocabulario_legal": "Puedo definir términos jurídicos, BOE y sentencias. ¿Qué término legal necesitas?",
    "leyes_agent": "Especialista en leyes, normativas y ordenanzas de Pamplona y Navarra. ¿Qué normativa necesitas?",
    # RRHH
    "rrhh": "Puedo gestionar empleados, horarios, vacaciones y nóminas. ¿Qué tarea de RRHH necesitas?",
    "laboral": "Especialista en contratos, Seguridad Social y despidos. ¿Qué consulta laboral tienes?",
    "rrhh_camaras": "Puedo gestionar cámaras de seguridad, videovigilancia y LOPD. ¿Qué necesitas?",
    # SISTEMA
    "tailscale": "Puedo conectar dispositivos a Tailscale y gestionar VPN. ¿Qué dispositivo quieres conectar?",
    "automatizador": "Puedo crear workflows n8n y automatizar procesos. ¿Qué proceso quieres automatizar?",
    "automatizacion": "Puedo automatizar ratón, teclado y crear macros. ¿Qué automatización necesitas?",
    "conectividad": "Puedo gestionar Cloudflare, túneles, IP y VPS. ¿Qué problema de conectividad tienes?",
    "red_telefonia": "Especialista en WiFi, router, Movistar y datos móviles. ¿Qué problema telefónico tienes?",
    "hardware": "Puedo gestionar TPV, impresoras, servidores y mantenimiento. ¿Qué problema de hardware tienes?",
    "scheduler": "Puedo programar tareas, cron, recordatorios y agendas. ¿Qué tarea quieres programar?",
    "gobierno": "Puedo gestionar trámites de gobierno y sede electrónica. ¿Qué trámite necesitas?",
    "sistemas": "Puedo monitorizar, administrar y gestionar servicios. ¿Qué tarea de sistemas necesitas?",
    "red": "Puedo monitorizar red, detectar anomalías y tráfico. ¿Qué problema de red tienes?",
    "backup": "Puedo crear copias de seguridad, snapshots y restaurar. ¿Qué necesitas respaldar?",
    "seguridad": "Puedo configurar firewall, antivirus y blindaje. ¿Qué medida de seguridad necesitas?",
    "rendimiento": "Puedo monitorizar CPU, RAM y rendimiento del sistema. ¿Qué recurso necesitas analizar?",
    "instalador": "Puedo instalar, desinstalar paquetes con brew y pip. ¿Qué software necesitas instalar?",
    # DOCUMENTOS
    "documentos_pdf": "Puedo leer PDF y extraer texto. ¿Qué PDF necesitas procesar?",
    "documentos_texto": "Puedo procesar texto, txt, markdown y rtf. ¿Qué documento de texto necesitas?",
    "documentos_word": "Puedo leer y editar documentos Word. ¿Qué documento Word necesitas?",
    "documentos_excel": "Puedo procesar hojas de cálculo Excel y tablas. ¿Qué archivo Excel necesitas?",
    "documentos_presentaciones": "Puedo gestionar presentaciones PowerPoint. ¿Qué presentación necesitas?",
    "orquestador_documentacion": "Puedo coordinar documentos y gestionar biblioteca. ¿Qué flujo documental necesitas?",
    "archivist": "Puedo archivar, controlar versiones y mantener historial. ¿Qué documento necesitas archivar?",
    "librarian": "Puedo gestionar biblioteca, catálogo y referencias. ¿Qué libro o documento necesitas?",
    "biblioteca": "Puedo buscar documentación, manuales y referencias. ¿Qué documento necesitas?",
    "bibliotecario_pasillo": "Puedo gestionar índices, catálogos e inventarios. ¿Qué código necesitas buscar?",
    # COMUNICACIÓN
    "email": "Puedo enviar correos, gestionar bandeja y buzones. ¿Qué email necesitas enviar?",
    "notificaciones": "Puedo enviar alertas, avisos y notificaciones push. ¿Qué notificación necesitas?",
    "conversacion": "Hola, soy URA. ¿En qué puedo ayudarte hoy?",
    "telegram_dam": "Puedo gestionar autorizaciones, aprobar y rechazar por Telegram. ¿Qué autorización necesitas?",
    "notificador_dam": "Puedo enviar notificaciones urgentes por Pushover, Twilio y WhatsApp. ¿Qué alerta necesitas?",
    # IA/CONOCIMIENTO
    "investigador_ia": "Puedo investigar modelos de IA, herramientas y tendencias. ¿Qué tema de IA necesitas investigar?",
    "conciencia": "Soy URA, tengo autoconocimiento y memoria. ¿Qué necesitas saber sobre mí?",
    "memoria": "Puedo recordar, almacenar y recuperar información. ¿Qué necesitas recordar?",
    "lenguaje": "Puedo procesar lenguaje, traducir y hacer NLP. ¿Qué tarea de lenguaje necesitas?",
    "vocabulario": "Puedo definir palabras, sinónimos y diccionarios. ¿Qué palabra necesitas definir?",
    "vocabulario_codigo": "Puedo explicar código, sintaxis, APIs y funciones. ¿Qué concepto de código necesitas?",
    "vocabulario_tecnico": "Puedo definir términos técnicos e informáticos. ¿Qué término técnico necesitas?",
    "vocabulario_bar": "Puedo explicar términos de hostelería y cocina profesional. ¿Qué término necesitas?",
    "modelos": "Puedo descargar modelos de Ollama y gestionar IA. ¿Qué modelo necesitas?",
    "lenguaje_escribiente": "Puedo redactar informes, escribir documentación. ¿Qué texto necesitas redactar?",
    "lenguaje_tecnico": "Puedo crear documentación técnica y manuales. ¿Qué documento técnico necesitas?",
    # SUPERVISIÓN
    "verificador": "Puedo verificar instalaciones y validar sistemas. ¿Qué necesitas verificar?",
    "auditor": "Puedo hacer auditorías, registros y trazabilidad. ¿Qué necesitas auditar?",
    "auditor_externo": "Puedo auditar GitHub, Reddit y webs externas. ¿Qué fuente externa necesitas auditar?",
    "supervisor": "Puedo supervisar y monitorizar todo el sistema. ¿Qué necesitas supervisar?",
    "revisor": "Puedo revisar código y detectar bugs. ¿Qué código necesitas revisar?",
    "reparador": "Puedo reparar errores y hacer auto-reparación. ¿Qué error necesitas reparar?",
    "guardian_residente": "Puedo vigilar carpetas y detectar intrusos. ¿Qué carpeta necesitas vigilar?",
    # ESPECIALES
    "motor_autorizacion_dual": "Puedo validar autorizaciones dobles ALFA y OMEGA. ¿Qué autorización necesitas validar?",
    "doble_verificacion": "Puedo gestionar 2FA, FaceID, TouchID y email. ¿Qué verificación necesitas?",
    "servidor_validacion": "Puedo validar móvil, DAM y autorización remota. ¿Qué validación necesitas?",
    "camaras": "Puedo gestionar cámaras Dahua, videovigilancia y grabación. ¿Qué cámara necesitas configurar?",
    "asesor": "Puedo comparar, recomendar y ayudarte a decidir. ¿Qué necesitas comparar?",
    "tendencias_pamplona": "Puedo analizar menús de bares en Pamplona y competencia. ¿Qué análisis necesitas?",
    "opencode": "Puedo programar con IA usando OpenCode y DeepSeek. ¿Qué código necesitas generar?",
    "arquitectura": "Puedo diseñar sistemas y arquitectura software. ¿Qué arquitectura necesitas diseñar?",
    "clasificador": "Puedo clasificar intenciones y enrutar consultas. ¿Qué consulta necesitas clasificar?",
    "registry": "Puedo gestionar catálogos, registros e inventarios. ¿Qué registro necesitas?",
    # VISIÓN/GUI
    "vision": "Puedo ver pantalla, capturar imágenes y hacer OCR. ¿Qué imagen necesitas analizar?",
    "gui": "Puedo hacer clic, mover ratón y controlar interfaz. ¿Qué acción de GUI necesitas?",
    # ORQUESTACIÓN
    "busqueda": "Puedo buscar en internet, noticias y webs. ¿Qué información necesitas buscar?",
    "orquestador_documentacion": "Puedo coordinar documentos y flujo documental. ¿Qué flujo necesitas orquestar?",
}


def improve_agent_file(file_path: Path, intent: str):
    """Mejora el método procesar() de un agente."""
    if intent not in IMPROVED_RESPONSES:
        return False

    content = file_path.read_text()

    # Buscar el método procesar existente y actualizar su return
    procesar_pattern = r'(def procesar\(self, texto: str\) -> str:\s+""".*?""".*?return f")Agente .*? procesando: \{texto\}"'

    if re.search(procesar_pattern, content, re.DOTALL):
        # Actualizar la respuesta existente
        improved_response = IMPROVED_RESPONSES[intent]
        new_return = f'\\1{improved_response}"'
        content = re.sub(procesar_pattern, new_return, content, count=1, flags=re.DOTALL)
        file_path.write_text(content)
        return True

    return False


def main():
    agents_dir = Path("/Users/ramonesnaola/URA/ura_ia_1972/agents")

    improved = 0
    for intent in IMPROVED_RESPONSES:
        # Mapear intent a nombre de archivo
        file_name = f"agente_{intent}.py"
        file_path = agents_dir / file_name

        if file_path.exists():
            if improve_agent_file(file_path, intent):
                improved += 1
                print(f"✓ Mejorado: {file_name}")
            else:
                print(f"- Ya tiene procesar: {file_name}")
        else:
            print(f"✗ No existe: {file_name}")

    print(f"\nTotal mejorados: {improved}/{len(IMPROVED_RESPONSES)}")


if __name__ == "__main__":
    main()
