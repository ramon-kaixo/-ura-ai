#!/bin/bash
if python3 -c "from core.boveda_manager import Boveda; Boveda().verificar_integridad()" 2>/dev/null; then
    export AWS_ACCESS_KEY_ID="$(python3 -c "from core.boveda_manager import Boveda; print(Boveda().recuperar('AWS_ACCESS_KEY_ID'))")"
    export AWS_SECRET_ACCESS_KEY="$(python3 -c "from core.boveda_manager import Boveda; print(Boveda().recuperar('AWS_SECRET_ACCESS_KEY'))")"
else
    echo "⚠️  Bóveda no disponible. Usando variables de entorno."
    export AWS_ACCESS_KEY_ID="${AWS_ACCESS_KEY_ID:-}"
    export AWS_SECRET_ACCESS_KEY="${AWS_SECRET_ACCESS_KEY:-}"
fi
if [ -z "$AWS_ACCESS_KEY_ID" ] || [ -z "$AWS_SECRET_ACCESS_KEY" ]; then
    echo "🔴 Credenciales AWS no encontradas ni en Bóveda ni en variables de entorno."
    echo "   Define AWS_ACCESS_KEY_ID y AWS_SECRET_ACCESS_KEY o guárdalas en la Bóveda."
    exit 1
fi
