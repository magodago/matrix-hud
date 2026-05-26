# 🕶️ MATRIX HUD

Monitor de agentes Matrix en tiempo real. Dorado sobre negro.

## Local

```bash
python hud_server.py
# → http://localhost:3333
```

## Despliegue (Render.com)

1. Sube este repo a GitHub
2. En Render.com → New Web Service → conecta el repo
3. Start Command: `python hud_server.py`
4. Render asigna una URL como `https://matrix-hud.onrender.com`

## Actualizar estado de agentes

```bash
curl -X POST https://tu-url.onrender.com/update \
  -H 'Content-Type: application/json' \
  -d '{"agent":"trinity","status":"working","task":"codificando...","progress":42}'
```

## Agentes incluidos

| Agente | Rol |
|--------|-----|
| 🧠 Morpheus | Estratega |
| 💻 Trinity | Ejecutora |
| 💪 Tank | Heavy Lifter |
| 🎭 Switch | Comodín |
| 🔍 Smith | Cazador |
| 🔮 Oracle | Analítica |
| 🔑 Keymaker | Herramientas |
| 🎨 Sati | Creativa |
| 🧪 Mouse | Prototipos |
| 🛡️ Apoc | Soporte |
