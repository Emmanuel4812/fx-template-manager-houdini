# FX Template Manager
**Shelf tool para Houdini** que permite explorar, previsualizar y hacer merge de escenas FX template directamente desde la interfaz de Houdini.

![Python](https://img.shields.io/badge/Python-3.9-blue) ![Houdini](https://img.shields.io/badge/Houdini-19.5-orange) ![PySide2](https://img.shields.io/badge/UI-PySide2-green)

---

## ¿Qué hace?

Cuando trabajas con FX en Houdini acumulás una librería de escenas template: explosiones, fluidos, partículas, simulaciones de tela, etc. Esta herramienta te da una interfaz visual para navegar esa librería, ver un preview del efecto y hacer merge a tu escena actual — todo sin salir de Houdini.

---

## Características

- **Listado visual** de todos los templates disponibles en una carpeta
- **Preview de imágenes** directamente en la interfaz
- **Abrir video** del preview con el reproductor del sistema
- **Buscador** para filtrar templates por nombre
- **Merge** directo con la escena abierta (equivalente a `File > Merge` / `Alt+M`)
- **Cambio de ruta** dinámico sin reiniciar la herramienta
- **Configuración persistente** entre sesiones

---

## Estructura esperada de carpetas

```
D:\escenasHoudiniRecursosVarios\
│
├── explosions\
│   ├── explosion_setUp.hip       ← escena principal
│   ├── video\
│   │   └── preview.mp4           ← video del efecto
│   └── geo\
│
├── bubblesSparklingWater\
│   ├── bubblesSparklingWater_v004.hip
│   ├── video\
│   │   └── bubblesSparklingWater_v002.mp4
│   └── ...
│
└── myEffect\
    ├── myEffect.hip
    └── preview\
        └── thumbnail.png         ← imagen estática como alternativa
```

**Reglas:**
- Cada carpeta debe tener al menos un `.hip` para aparecer en la lista
- Los previews se buscan en subcarpetas llamadas `video`, `videos`, `preview` o `previews`
- Soporta video: `.mp4 .mov .avi .webm` e imagen: `.png .jpg .jpeg .exr`

---

## Instalación

### 1. Copiar los archivos

Coloca la carpeta del proyecto en una ruta fija, por ejemplo:
```
D:\scene_manager_houdini\
```

### 2. Agregar al shelf desde la Python Shell de Houdini

Abre Houdini, presiona **Alt + E** y pega lo siguiente:

```python
import hou

script = (
    "import sys; "
    "sys.path.insert(0, r'D:\\scene_manager_houdini'); "
    "import importlib, fx_template_manager_v3; "
    "importlib.reload(fx_template_manager_v3); "
    "fx_template_manager_v3.show()"
)

tool = hou.shelves.newTool(
    name="fx_template_manager",
    label="FX Templates",
    script=script,
    icon="BUTTONS_layout_view"
)

shelf = hou.shelves.shelves()["fx_tools"]
shelf.setTools(shelf.tools() + (tool,))
print("Listo!")
```

> Si no tienes un shelf llamado `fx_tools`, reemplaza `"fx_tools"` por el nombre del shelf donde quieres el botón, o créalo con `hou.shelves.newShelf("fx_tools", "FX Tools")`.

---

## Uso

1. Haz click en el botón **FX Templates** en tu shelf
2. Explora la lista de templates (izquierda)
3. Haz click en un template para ver su preview e información
4. Si tiene video, haz click en **Abrir video preview**
5. Haz click en **Merge con escena abierta** para importarlo

---

## Abrir manualmente (sin shelf)

Si necesitas abrirlo desde la Python Shell:

```python
import sys
sys.path.insert(0, r"D:\scene_manager_houdini")
import importlib, fx_template_manager_v3
importlib.reload(fx_template_manager_v3)
fx_template_manager_v3.show()
```

---

## Cambiar la ruta de templates

**Opción A — Desde la interfaz:**  
Click en el botón **Cambiar ruta** dentro de la herramienta. La nueva ruta se guarda automáticamente.

**Opción B — Editar config directamente:**  
Edita el archivo:
```
C:\Users\<TuUsuario>\.houdini\fx_template_manager_config.json
```
```json
{
  "template_path": "D:\\escenasHoudiniRecursosVarios"
}
```

---

## Archivos del proyecto

| Archivo | Descripción |
|---|---|
| `fx_template_manager_v3.py` | Script principal — **el único que necesitas** |
| `fx_template_manager_console.py` | Versión de respaldo sin UI (solo consola) |
| `validate_templates.py` | Utilidad para validar la estructura de carpetas |

---

## Requisitos

| Componente | Versión |
|---|---|
| Houdini | 19.5+ |
| Python | 3.9 (incluido en Houdini) |
| PySide2 | (incluido en Houdini) |
| hdefereval | (módulo interno de Houdini) |

---

## Notas técnicas

Algunos errores encontrados durante el desarrollo y cómo se resolvieron:

| Error | Causa | Solución |
|---|---|---|
| `No module named 'hou.qt'` | No existe en H19.5 | Usar `QApplication.topLevelWidgets()` para encontrar la ventana principal |
| Python Shell se congela | Qt bloquea el event loop | Usar `hdefereval.executeDeferred()` |
| `hipFile has no attribute 'mergeHipFile'` | API incorrecta | El método correcto es `hou.hipFile.merge()` |
| `Shelf has no attribute 'addTool'` | API incorrecta | El método correcto es `shelf.setTools(shelf.tools() + (tool,))` |
| `Shelf has no attribute 'save'` | No existe | Houdini guarda automáticamente, no hace falta |
| `shelves()` returns dict | Se iteraba como lista | Acceder con `shelves()["nombre_shelf"]` |

---

## Posibles mejoras futuras

- [ ] Thumbnails generados automáticamente desde el `.hip`
- [ ] Categorías o tags por tipo de efecto
- [ ] Historial de templates usados recientemente
- [ ] Soporte para múltiples rutas de templates
- [ ] Preview de video embebido en la interfaz (QMediaPlayer)
- [ ] Descripción editable por template (archivo `.txt` o `.json` en la carpeta)
