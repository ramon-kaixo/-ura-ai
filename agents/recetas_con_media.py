"""
RECETAS CON VARIANTES Y MEDIA
Incluye 3 recetas por plato + fotos + vídeos de fuentes confiables
"""

from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "board.db"

VARIANTES_RECETAS = {
    "Paella Valenciana": {
        "cocina": "española",
        "variantes": [
            {
                "nombre": "Paella Valenciana Tradicional",
                "ingredientes": "arroz senia, pollo, conejo, judías verdes, garrofón, tomate, azafrán, romero, aceite, sal",
                "elaboracion": "1. Sofreír pollo y conejo. 2. Añadir verduras y tomate. 3. Incorporar caldo caliente. 4. Añadir arroz y azafrán. 5. Cocer 18 min. 6. Reposar 5 min con papel foil.",
                "notas": "La tradición marca que NO se remueve el arroz al final. El socarrat (fondo tostado) es la parte más valorada.",
                "tiempo": "1h 15min",
                "dificultad": "media",
                "fotos": [
                    {
                        "url": "https://images.unsplash.com/photo-1534482421-64566f976cfa?w=800",
                        "fuente": "Unsplash",
                        "descripcion": "Paella terminada",
                    },
                    {
                        "url": "https://images.unsplash.com/photo-1534483500483-4827ac2f4b5b?w=800",
                        "fuente": "Unsplash",
                        "descripcion": "Detalle del socarrat",
                    },
                ],
                "videos": [
                    {
                        "url": "https://www.youtube.com/results?search_query=paella+valenciana+receta+autentica",
                        "fuente": "YouTube",
                        "descripcion": "Búsqueda vídeos paella auténtica",
                    }
                ],
                "fuente": "Directo al Paladar",
            },
            {
                "nombre": "Paella de Mariscos",
                "ingredientes": "arroz, gambas, mejillones, calamares, sepia, ajo, cebolla, pimiento, tomate, fumet, azafrán, aceite",
                "elaboracion": "1. Preparar fumet con cabezas de gamba. 2. Sofreír base de ajo, cebolla, pimiento. 3. Añadir tomate y calamares. 4. Incorporar arroz y caldo. 5. Añadir mariscos y azafrán. 6. 18 min de cocción.",
                "notas": "El fumet de marisco es clave. Podeis añadir almejas y berberechos.",
                "tiempo": "1h",
                "dificultad": "media",
                "fotos": [
                    {
                        "url": "https://images.unsplash.com/photo-1563379926898-05f4575a45d8?w=800",
                        "fuente": "Unsplash",
                        "descripcion": "Paella de mariscos",
                    }
                ],
                "videos": [
                    {
                        "url": "https://www.youtube.com/results?search_query=paella+mariscos+receta",
                        "fuente": "YouTube",
                        "descripcion": "Paella de mariscos",
                    }
                ],
                "fuente": "Canal Cocina",
            },
            {
                "nombre": "Arroz Negro (Paella negra)",
                "ingredientes": "arroz, calamares, tinta de calamar, fumet, cebolla, ajo, pimiento, tomate, aceite, alioli",
                "elaboracion": "1. Preparar sofrito base. 2. Añadir arroz y sofreír 2 min. 3. Incorporar tinta y caldo. 4. Cocer 18 min. 5. Servir con alioli.",
                "notas": "La tinta debe añadirse con el caldo para un color uniforme. Imprescindible el alioli.",
                "tiempo": "45 min",
                "dificultad": "media",
                "fotos": [
                    {
                        "url": "https://images.unsplash.com/photo-1534939561126-855b8675edd7?w=800",
                        "fuente": "Unsplash",
                        "descripcion": "Arroz negro con alioli",
                    }
                ],
                "videos": [
                    {
                        "url": "https://www.youtube.com/results?search_query=arroz+negro+receta",
                        "fuente": "YouTube",
                        "descripcion": "Arroz negro",
                    }
                ],
                "fuente": "Recetas de Escándalo",
            },
        ],
    },
    "Macarrones a la Boloñesa": {
        "cocina": "española",
        "variantes": [
            {
                "nombre": "Macarrones Boloñesa Clásica",
                "ingredientes": "macarrones, carne picada ternera, cebolla, zanahoria, apio, tomate triturado, vino tinto, aceite, sal, pimienta, queso parmesano",
                "elaboracion": "1. Picar finas cebolla, zanahoria, apio (soffritto). 2. Sofrerir a fuego lento 15 min. 3. Añadir carne y cocinar hasta que pierda el agua. 4. Flambear con vino tinto. 5. Añadir tomate y cocinar 45 min. 6. Cocer pasta al dente. 7. Mezclar.",
                "notas": "El soffritto bien hecho es la base. Cocinar la salsa mínimo 45 min.",
                "tiempo": "1h 15min",
                "dificultad": "baja",
                "fotos": [
                    {
                        "url": "https://images.unsplash.com/photo-1555949258-eb67b1ef0ceb?w=800",
                        "fuente": "Unsplash",
                        "descripcion": "Macarrones boloñesa",
                    }
                ],
                "videos": [
                    {
                        "url": "https://www.youtube.com/results?search_query=macarrones+boloñesa+receta",
                        "fuente": "YouTube",
                        "descripcion": "Boloñesa clásica",
                    }
                ],
                "fuente": "Directo al Paladar",
            },
            {
                "nombre": "Macarrones al Horno",
                "ingredientes": "macarrones, ragú boloñesa, bechamel, queso mozzarella, queso parmesano, mantequilla, harina, leche",
                "elaboracion": "1. Preparar boloñesa. 2. Hacer bechamel. 3. Cocer pasta. 4. Mezclar pasta con boloñesa. 5. Montar en bandeja con capas: pasta, bechamel, queso. 6. Gratinar 20 min a 180°C.",
                "notas": "Podeis añadir jamón york entre capas para más sabor.",
                "tiempo": "1h 30min",
                "dificultad": "media",
                "fotos": [
                    {
                        "url": "https://images.unsplash.com/photo-1574894709920-11b28e7367e3?w=800",
                        "fuente": "Unsplash",
                        "descripcion": "Macarrones al horno gratinados",
                    }
                ],
                "videos": [
                    {
                        "url": "https://www.youtube.com/results?search_query=macarrones+horno+boloñesa",
                        "fuente": "YouTube",
                        "descripcion": "Macarrones al horno",
                    }
                ],
                "fuente": "Canal Cocina",
            },
            {
                "nombre": "Macarrones Express",
                "ingredientes": "macarrones, carne picada, tomate frito, cebolla, ajo, aceite, sal, orégano, queso",
                "elaboracion": "1. Cocer pasta. 2. Sofrerir cebolla y ajo. 3. Añadir carne y cocinar. 4. Incorporar tomate frito. 5. Mezclar con pasta. 6. Añadir queso.",
                "notas": "Versión rápida usando tomate frito. Ideal para días con poco tiempo.",
                "tiempo": "25 min",
                "dificultad": "baja",
                "fotos": [
                    {
                        "url": "https://images.unsplash.com/photo-1551183053-bf91a1d81141?w=800",
                        "fuente": "Unsplash",
                        "descripcion": "Macarrones rápidos",
                    }
                ],
                "videos": [],
                "fuente": "Recetas Fáciles",
            },
        ],
    },
    "Ceviche": {
        "cocina": "peruana",
        "variantes": [
            {
                "nombre": "Ceviche Clásico Peruano",
                "ingredientes": "corvina o lenguado fresco, limón, cebolla morada, ají amarillo, cilantro, sal, pimienta, camote sancochado, maíz choclo",
                "elaboracion": "1. Cortar pescado en cubos de 2-3 cm. 2. Sazonar con sal y pimienta. 3. Dejar reposar 5 min. 4. Exprimir limones y hacer leche de tigre. 5. Cortar cebolla en juliana fina. 6. Mezclar todo y añadir ají amarillo en rodajas. 7. Añadir cilantro. 8. Servir inmediatamente con camote y maíz.",
                "notas": "El pescado DEBE estar muy fresco. El tiempo de 'cocción' en limón es de 3-5 minutos máximo.",
                "tiempo": "30 min",
                "dificultad": "media",
                "fotos": [
                    {
                        "url": "https://images.unsplash.com/photo-1535399831218-d5bd36d1a6b3?w=800",
                        "fuente": "Unsplash",
                        "descripcion": "Ceviche clásico",
                    },
                    {
                        "url": "https://images.unsplash.com/photo-1553621042-f6e147245754?w=800",
                        "fuente": "Unsplash",
                        "descripcion": "Ceviche con camote",
                    },
                ],
                "videos": [
                    {
                        "url": "https://www.youtube.com/results?search_query=ceviche+peruano+receta+autentica",
                        "fuente": "YouTube",
                        "descripcion": "Ceviche auténtico",
                    }
                ],
                "fuente": "Laylita",
            },
            {
                "nombre": "Ceviche de Pulpo",
                "ingredientes": "pulpo cocido, limón, cebolla morada, ají amarillo, cilantro, aceite de oliva, sal",
                "elaboracion": "1. Cortar pulpo en rodajas. 2. Sazonar con sal. 3. Añadir limón y aceite. 4. Incorporar cebolla y ají. 5. Decorar con cilantro.",
                "notas": "Si el pulpo es crudo, hervir 40-50 min con cebolla y laurel.",
                "tiempo": "20 min",
                "dificultad": "baja",
                "fotos": [
                    {
                        "url": "https://images.unsplash.com/photo-1565557623262-b51c2513a641?w=800",
                        "fuente": "Unsplash",
                        "descripcion": "Ceviche de pulpo",
                    }
                ],
                "videos": [],
                "fuente": "Recetas Grilleras",
            },
            {
                "nombre": "Tiradito",
                "ingredientes": "lenguado en láminas finas, limón, ají amarillo,酱油, aceite, chalota, Hinojo",
                "elaboracion": "1. Cortar pescado en láminas finas al bies. 2. Hacer salsa con limón, ají y酱油. 3. Bañar el pescado. 4. Decorar con chalota y hinojo.",
                "notas": "Técnica japonesa mezclada con peruana. Similar al sashimi pero con marinada.",
                "tiempo": "25 min",
                "dificultad": "media",
                "fotos": [
                    {
                        "url": "https://images.unsplash.com/photo-1579584425555-c3ce17fd4351?w=800",
                        "fuente": "Unsplash",
                        "descripcion": "Tiradito",
                    }
                ],
                "videos": [],
                "fuente": "Gastronomía Peruana",
            },
        ],
    },
    "Tacos al Pastor": {
        "cocina": "mexicana",
        "variantes": [
            {
                "nombre": "Tacos al Pastor Tradicionales",
                "ingredientes": "carné cerdo en adobo, piña, cebolla, cilantro, tortillas de maíz pequeñas, chile guajillo, achiote, vinagre, ajo, orégano, comino",
                "elaboracion": "1. Preparar adobo con chiles, achiote, vinagre, ajo, especias. 2. Marinar carne 12-24h. 3. Cocinar en trompo o plancha muy caliente. 4. Cortar fino con lascripción vertical. 5. Servir en tortilla con piña, cebolla, cilantro.",
                "notas": "El adobo es clave. Podeis usar barbacoa o kiln para sabor auténtico. Tiempo mínimo de marinado 4h.",
                "tiempo": "24h marinado + 30min cocción",
                "dificultad": "alta",
                "fotos": [
                    {
                        "url": "https://images.unsplash.com/photo-1551504734-5ee1c4a1479b?w=800",
                        "fuente": "Unsplash",
                        "descripcion": "Tacos al pastor",
                    },
                    {
                        "url": "https://images.unsplash.com/photo-1599974579688-8dbdd335c77f?w=800",
                        "fuente": "Unsplash",
                        "descripcion": "Trompo de pastor",
                    },
                ],
                "videos": [
                    {
                        "url": "https://www.youtube.com/results?search_query=tacos+al+pastor+receta+autentica",
                        "fuente": "YouTube",
                        "descripcion": "Tacos al pastor",
                    }
                ],
                "fuente": "Directo al Paladar México",
            },
            {
                "nombre": "Tacos de Carnitas",
                "ingredientes": "pierna cerdo, naranja, ajo, canela, cloves, laurel, epidios, tortillas, cebolla, cilantro, salsa verde",
                "elaboracion": "1. Cortar cerdo en trozos grandes. 2. Cocinar lento en líquido con naranja, especias 3-4h hasta que esté tierno. 3. Desmenuzar. 4. Freír en su propia grasa para crujiente. 5. Servir en tortilla con cebolla y cilantro.",
                "notas": "La doble cocción (guiso + frito) da la textura perfecta. Podeis añadir oregano.",
                "tiempo": "4h",
                "dificultad": "media",
                "fotos": [
                    {
                        "url": "https://images.unsplash.com/photo-1624300629298-e9de39c13be5?w=800",
                        "fuente": "Unsplash",
                        "descripcion": "Tacos de carnitas",
                    }
                ],
                "videos": [
                    {
                        "url": "https://www.youtube.com/results?search_query=carnitas+receta+mexicana",
                        "fuente": "YouTube",
                        "descripcion": "Carnitas caseras",
                    }
                ],
                "fuente": "Mexicanisimo",
            },
            {
                "nombre": "Tacos de Pollo",
                "ingredientes": "pechuga pollo, chile chipotle, crema, cebolla, ajo, comino, cilantro, lime, tortillas",
                "elaboracion": "1. Sazonar pollo con especias. 2. Cocinar a la plancha. 3. Desmenuzar. 4. Mezclar con adobo de chipotle y crema. 5. Servir con cebolla, cilantro, lime.",
                "notas": "Versión más ligera. Podeis usar muslo para más jugosidad.",
                "tiempo": "30 min",
                "dificultad": "baja",
                "fotos": [
                    {
                        "url": "https://images.unsplash.com/photo-1565299585323-38d6b0865b47?w=800",
                        "fuente": "Unsplash",
                        "descripcion": "Tacos de pollo",
                    }
                ],
                "videos": [],
                "fuente": "Comida Mexicana Fácil",
            },
        ],
    },
    "Carbonara": {
        "cocina": "italiana",
        "variantes": [
            {
                "nombre": "Carbonara Originale",
                "ingredientes": "spaghetti, guanciale, yemas de huevo, pecorino romano, pimienta negra, sal",
                "elaboracion": "1. Cocer pasta en agua con sal (no añadir aceite). 2. Cortar guanciale en tacos y dorar sin quemar. 3. Batir yemas con pecorino rallado. 4. Añadir pimienta negra molida. 5. ESCURDIR pasta y añadir a guanciale FUERA del fuego. 6. Añadir mezcla de yemas y remover rápidamente. 7. Añadir más agua de pasta si needed.",
                "notas": "NUNCA usar bacon. NUNCA usar nata. La clave es temperatura: fuera del fuego para no cuajar los eggs.",
                "tiempo": "20 min",
                "dificultad": "media",
                "fotos": [
                    {
                        "url": "https://images.unsplash.com/photo-1612874742237-6526221588e3?w=800",
                        "fuente": "Unsplash",
                        "descripcion": "Carbonara italiana",
                    },
                    {
                        "url": "https://images.unsplash.com/photo-1555949258-eb67b1ef0ceb?w=800",
                        "fuente": "Unsplash",
                        "descripcion": "Detalle carbonara",
                    },
                ],
                "videos": [
                    {
                        "url": "https://www.youtube.com/results?search_query=carbonara+italiana+originale+ricetta",
                        "fuente": "YouTube",
                        "descripcion": "Carbonara auténtica italiana",
                    }
                ],
                "fuente": "Giallo Zafferano",
            },
            {
                "nombre": "Carbonara con Pancetta",
                "ingredientes": "spaghetti, pancetta, yemas, pecorino, parmesano, pimienta negra, sal",
                "elaboracion": "Igual que la original pero usando pancetta en lugar de guanciale. Dacuración de pancetta 10 min.",
                "notas": "Versión más fácil de encontrar fuera de Italia. El sabor es muy similar.",
                "tiempo": "20 min",
                "dificultad": "baja",
                "fotos": [
                    {
                        "url": "https://images.unsplash.com/photo-1598866594230-a7c12756260f?w=800",
                        "fuente": "Unsplash",
                        "descripcion": "Carbonara con pancetta",
                    }
                ],
                "videos": [],
                "fuente": "Cooknsolo",
            },
            {
                "nombre": "Carbonara Vegetariana (Cacio e Pepe)",
                "ingredientes": "spaghetti, pecorino romano, pimienta negra, sal, aceite",
                "elaboracion": "1. Cocer pasta. 2. Tostar pimienta en seco. 3. Añadir pasta con un poco de agua. 4. Añadir pecorino rallado fino y remover. 5. La emulación con el agua de pasta crea la salsa.",
                "notas": "No lleva huevo, es la versión más romana. El truco está en la temperatura del queso.",
                "tiempo": "15 min",
                "dificultad": "media",
                "fotos": [
                    {
                        "url": "https://images.unsplash.com/photo-1563379926898-05f4575a45d8?w=800",
                        "fuente": "Unsplash",
                        "descripcion": "Cacio e Pepe",
                    }
                ],
                "videos": [],
                "fuente": "Roma Today",
            },
        ],
    },
}


def init_recetas_con_media():
    from agents.agente_media_recetas import (
        agregar_foto_receta,
        agregar_video_receta,
        init_media_recetas,
    )

    init_media_recetas()

    for _receta_base, data in VARIANTES_RECETAS.items():
        cocina = data["cocina"]

        for variante in data["variantes"]:
            nombre_variante = variante["nombre"]
            variante["ingredientes"]

            for foto in variante.get("fotos", []):
                agregar_foto_receta(
                    receta_nombre=nombre_variante,
                    cocina=cocina,
                    url=foto["url"],
                    fuente=foto["fuente"],
                    descripcion=foto["descripcion"],
                )

            for video in variante.get("videos", []):
                agregar_video_receta(
                    receta_nombre=nombre_variante,
                    cocina=cocina,
                    url=video["url"],
                    fuente=video["fuente"],
                    descripcion=video["descripcion"],
                )

    return len(VARIANTES_RECETAS)


def obtener_receta_completa(nombre):
    if nombre in VARIANTES_RECETAS:
        data = VARIANTES_RECETAS[nombre]
        return {"base": nombre, "cocina": data["cocina"], "variantes": data["variantes"]}
    return None


def buscar_receta(nombre):
    resultados = []
    for base, data in VARIANTES_RECETAS.items():
        if nombre.lower() in base.lower():
            resultados.append(
                {"base": base, "cocina": data["cocina"], "num_variantes": len(data["variantes"])}
            )
    return resultados


VARIANTES_RECETAS.update(
    {
        "Lentejas con Chorizo": {
            "cocina": "española",
            "variantes": [
                {
                    "nombre": "Lentejas Castellanas Tradicionales",
                    "ingredientes": "lentejas castellanas, chorizo, morcilla, cebolla, zanahoria, pimiento, tomate, ajo, laurel, aceite, sal",
                    "elaboracion": "1. Poner lentejas en remojo 8h. 2. Sofrenir verduras. 3. Añadir chorizo y morcilla. 4. Incorporar lentejas y agua. 5. Hervir y cocinar lento 1.5h.",
                    "notas": "No añadir sal hasta el final o se endurecen.",
                    "tiempo": "2h + remojo",
                    "dificultad": "baja",
                    "fotos": [
                        {
                            "url": "https://images.unsplash.com/photo-1547592180-85f173990554?w=800",
                            "fuente": "Unsplash",
                            "descripcion": "Lentejas con chorizo",
                        }
                    ],
                    "videos": [
                        {
                            "url": "https://www.youtube.com/results?search_query=lentejas+chorizo+receta",
                            "fuente": "YouTube",
                            "descripcion": "Lentejas tradicionales",
                        }
                    ],
                    "fuente": "Directo al Paladar",
                },
                {
                    "nombre": "Lentejas Estofadas",
                    "ingredientes": "lentejas, chorizo, carne cerdo, cebolla, ajo, pimentón, vino blanco, aceite",
                    "elaboracion": "1. Dorar chorizo y carne. 2. Sofrenir cebolla y ajo. 3. Añadir pimentón y vino. 4. Incorporar lentejas y caldo. 5. Estofar 1.5h.",
                    "notas": "El estofado da más sabor.",
                    "tiempo": "1h 30min",
                    "dificultad": "media",
                    "fotos": [],
                    "videos": [],
                    "fuente": "Recetas de Escándalo",
                },
                {
                    "nombre": "Lentejas con Arroz",
                    "ingredientes": "lentejas, arroz, chorizo, cebolla, ajo, pimentón, aceite",
                    "elaboracion": "1. Cocer lentejas hasta casi hechas. 2. Añadir arroz y chorizo. 3. Cocinar 15 min más.",
                    "notas": "Combinación típica de La Mancha.",
                    "tiempo": "1h 15min",
                    "dificultad": "baja",
                    "fotos": [],
                    "videos": [],
                    "fuente": "Canal Cocina",
                },
            ],
        },
        "Mole Poblano": {
            "cocina": "mexicana",
            "variantes": [
                {
                    "nombre": "Mole Poblano Tradicional",
                    "ingredientes": "chile mulato, chile ancho, chile pasilla, chocolate negro, almendras, cacahuates, pasas, ajo, cebolla, tomate, canela, clavo, comino, pavo",
                    "elaboracion": "1. Tostar y remojar chiles. 2. Freír almendras, cacahuates, pasas. 3. Asar tomates y especias. 4. Moler todo junto con caldo. 5. Cocinar a fuego bajo 2h. 6. Añadir chocolate al final.",
                    "notas": "El chocolate debe ser amargo. Mínimo 2h de cocción.",
                    "tiempo": "4h",
                    "dificultad": "alta",
                    "fotos": [
                        {
                            "url": "https://images.unsplash.com/photo-1599974579688-8dbdd335c77f?w=800",
                            "fuente": "Unsplash",
                            "descripcion": "Mole poblano",
                        }
                    ],
                    "videos": [
                        {
                            "url": "https://www.youtube.com/results?search_query=mole+poblano+receta",
                            "fuente": "YouTube",
                            "descripcion": "Mole poblano auténtico",
                        }
                    ],
                    "fuente": "Directo al Paladar México",
                },
                {
                    "nombre": "Mole Rojo Express",
                    "ingredientes": "chile guajillo, chile ancho, tomate, cebolla, ajo, comino, clavo, aceite, pollo",
                    "elaboracion": "1. Tostar y remojar chiles. 2. Hervir tomate y cebolla. 3. Moler todo. 4. Sofrreír pasta de mole. 5. Añadir caldo y cocinar 30 min.",
                    "notas": "Versión más rápida sin chocolate.",
                    "tiempo": "1h 15min",
                    "dificultad": "media",
                    "fotos": [],
                    "videos": [],
                    "fuente": "Mexicanisimo",
                },
                {
                    "nombre": "Mole Negro Oaxaqueño",
                    "ingredientes": "chile chilhuacle negro, chocolate, tortillas, plátano macho, tejocotes, almendra, ajonjolí, pavo",
                    "elaboracion": "1. Asar chiles hasta carbonizar. 2. Asar tortillas muy oscuras. 3. Freír plátano y tejocotes. 4. Moler todo con caldo. 5. Cocinar mole 3h.",
                    "notas": "El mole negro es el más complejo. Las tortillas quemadas son clave.",
                    "tiempo": "5h",
                    "dificultad": "muy alta",
                    "fotos": [],
                    "videos": [],
                    "fuente": "Gastronomía Oaxaqueña",
                },
            ],
        },
        "Tiramisú": {
            "cocina": "italiana",
            "variantes": [
                {
                    "nombre": "Tiramisú Clásico",
                    "ingredientes": "mascarpone, huevos, azúcar, café expreso, bizcochos savoiardi, cacao en polvo, amaretto",
                    "elaboracion": "1. Batir yemas con azúcar. 2. Añadir mascarpone. 3. Montar claras e incorporar. 4. Mojar bizcochos en café frío con amaretto. 5. Montar capas. 6. Enfriar mínimo 4h. 7. Espolvorear cacao.",
                    "notas": "NO usar nata. NO cocinar las yemas. Enfriar mínimo 4h.",
                    "tiempo": "30 min + frío",
                    "dificultad": "media",
                    "fotos": [
                        {
                            "url": "https://images.unsplash.com/photo-1571877227200-a0d98ea607e9?w=800",
                            "fuente": "Unsplash",
                            "descripcion": "Tiramisú",
                        },
                        {
                            "url": "https://images.unsplash.com/photo-1586040140378-b5634cb4c8fc?w=800",
                            "fuente": "Unsplash",
                            "descripcion": "Tiramisú detalle",
                        },
                    ],
                    "videos": [
                        {
                            "url": "https://www.youtube.com/results?search_query=tiramisú+receta",
                            "fuente": "YouTube",
                            "descripcion": "Tiramisú auténtico",
                        }
                    ],
                    "fuente": "Giallo Zafferano",
                },
                {
                    "nombre": "Tiramisú sin Huevos",
                    "ingredientes": "mascarpone, nata para montar, azúcar, café expreso, bizcochos, cacao, vainilla",
                    "elaboracion": "1. Montar nata con azúcar. 2. Añadir mascarpone y vainilla. 3. Mojar bizcochos en café frío. 4. Montar capas. 5. Enfriar 4h.",
                    "notas": "Versión más segura. Igual de cremoso.",
                    "tiempo": "25 min + frío",
                    "dificultad": "baja",
                    "fotos": [],
                    "videos": [],
                    "fuente": "Cooknsolo",
                },
                {
                    "nombre": "Tiramisú de Fresas",
                    "ingredientes": "mascarpone, huevos, azúcar, fresas, bizcochos, licor de fresa, cacao",
                    "elaboracion": "1. Preparar crema como clásico. 2. Cortar fresas y macerar con azúcar. 3. Alternar capas con fresas. 4. Terminar con cacao.",
                    "notas": "Versión primaveral.",
                    "tiempo": "35 min + frío",
                    "dificultad": "media",
                    "fotos": [],
                    "videos": [],
                    "fuente": "Dolci Italiani",
                },
            ],
        },
        "Lomo Saltado": {
            "cocina": "peruana",
            "variantes": [
                {
                    "nombre": "Lomo Saltado Original",
                    "ingredientes": "lomo de res, cebolla roja, tomate, ají amarillo, cebolla china, salsa soja, vinagre, comino, ajo, aceite, arroz, papas fritas",
                    "elaboracion": "1. Cortar lomo en filetitos. 2. Sazonar con ajo, comino, sal, pimienta. 3. Dorar carne en wok muy caliente. 4. Soffritir cebolla y tomate. 5. Añadir ají y salsa soja. 6. Servir sobre arroz con papas fritas.",
                    "notas": "El wok en llamas es fundamental para el sabor.",
                    "tiempo": "30 min",
                    "dificultad": "media",
                    "fotos": [
                        {
                            "url": "https://images.unsplash.com/photo-1512058564366-18510be2db19?w=800",
                            "fuente": "Unsplash",
                            "descripcion": "Lomo saltado",
                        }
                    ],
                    "videos": [
                        {
                            "url": "https://www.youtube.com/results?search_query=lomo+saltado+receta",
                            "fuente": "YouTube",
                            "descripcion": "Lomo saltado auténtico",
                        }
                    ],
                    "fuente": "Laylita",
                },
                {
                    "nombre": "Lomo Saltado de Pollo",
                    "ingredientes": "pechuga pollo, cebolla, tomate, ají amarillo, salsa soja, vinagre, comino, arroz, papas fritas",
                    "elaboracion": "Igual que el original pero usando pechuga de pollo.",
                    "notas": "Versión más económica y ligera.",
                    "tiempo": "25 min",
                    "dificultad": "baja",
                    "fotos": [],
                    "videos": [],
                    "fuente": "Recetas Peruanas",
                },
                {
                    "nombre": "Lomo Vestido",
                    "ingredientes": "lomo, cebolla, tomate, ají, huevos fritos, arroz, papas fritas, aceitunas, perejil",
                    "elaboracion": "1. Preparar lomo saltado. 2. Freír huevos. 3. Servir con huevo frito, aceitunas y perejil.",
                    "notas": "Versión completa con huevo frito.",
                    "tiempo": "35 min",
                    "dificultad": "media",
                    "fotos": [],
                    "videos": [],
                    "fuente": "Gastronomía Peruana",
                },
            ],
        },
    }
)

if __name__ == "__main__":
    count = init_recetas_con_media()
    print("=== RECETAS CON MEDIA ===")
    print(f"Recetas con variantes: {count}")

    print("\n📋 Receta completa - Paella:")
    completa = obtener_receta_completa("Paella Valenciana")
    if completa:
        print(f"Cocina: {completa['cocina']}")
        print(f"Variantes: {len(completa['variantes'])}")
        for v in completa["variantes"]:
            print(f"  • {v['nombre']}")
            print(f"    Fotos: {len(v.get('fotos', []))}")
            print(f"    Vídeos: {len(v.get('videos', []))}")
