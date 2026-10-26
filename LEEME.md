# Cazador de figuras 🎯

Bot que revisa **todo el día** 13 sitios buscando tus figuras (y sus cajas y piezas sueltas),
y te manda una **alerta al celular por Telegram con foto, precio, costo total puesto en Chile
y link directo a ZenMarket/Buyee** apenas aparece algo barato. Guarda todo en un panel web
con fotos y gráficos de precio.

Corre gratis en GitHub: tu notebook puede estar apagado.

## Dónde busca

| País | Sitio | Cada cuánto | Cómo compras |
|---|---|---|---|
| 🇯🇵 | **Mercari** (segunda mano) | 15 min | ZenMarket / Buyee (botón directo) |
| 🇯🇵 | **Yahoo Auctions + Yahoo Flea** | 15 min | ZenMarket / Buyee (botón directo) |
| 🇯🇵 | **Rakuma** (segunda mano) | 15 min | ZenMarket (pegar link) |
| 🇯🇵 | Mandarake (tienda de usados de anime) | 1 h | ZenMarket (pegar link) |
| 🇯🇵 | Suruga-ya, Lashinbang 💻 | 30 min | ZenMarket (pegar link) |
| 🇯🇵 | Rakuten, Yahoo Shopping | 1 h | ZenMarket (pegar link) |
| 🇯🇵 | Off Mall (Hard Off / Hobby Off) 💻 | 30 min | ZenMarket (pegar link) |
| 🇯🇵 | AmiAmi (sección usados) 💻 | 30 min | ZenMarket (pegar link) |
| 🇨🇳 | **Goofish 闲鱼** (busca en chino) 💻 | 30 min | Superbuy (pegar link) |
| 🌎 | eBay (suma el envío que cobra el vendedor) | 30 min | directo |

💻 = estos sitios bloquean a los servidores de GitHub, así que se revisan **desde tu notebook**
(sección "Sitios desde el notebook"), solo mientras esté encendido.
MercadoLibre Chile quedó fuera: ahora exige iniciar sesión incluso para ver resultados.

Los mercados de segunda mano se revisan más seguido porque ahí las gangas duran minutos;
las tiendas cambian lento. ZenMarket compra en *cualquier* tienda japonesa pegando el link.

---

## Instalación (≈15 minutos, desde el notebook)

### 1. Crea tu bot de Telegram (5 min)

1. Instala Telegram en el celular si no lo tienes.
2. Busca **@BotFather** (el que tiene ✔️ azul) y escríbele `/newbot`.
3. Ponle un nombre (ej. `Cazador Madoka`) y un usuario que termine en `bot` (ej. `jordan_cazador_bot`).
4. BotFather te responde con un **token** tipo `7712345678:AAH...`. Cópialo, es tu `TELEGRAM_TOKEN`.
5. Abre el chat con tu bot nuevo y mándale cualquier mensaje (ej. `hola`).
6. En el navegador abre (cambiando TU_TOKEN):
   `https://api.telegram.org/botTU_TOKEN/getUpdates`
   Busca `"chat":{"id":123456789` — ese número es tu `TELEGRAM_CHAT_ID`.

### 2. Sube el bot a GitHub (5 min)

1. Crea una cuenta gratis en <https://github.com> (si no tienes).
2. Arriba a la derecha **+ → New repository**. Nombre: `cazador-figuras`. Marca **Public**
   (así las ejecuciones son gratis e ilimitadas; solo se ven precios de listados públicos,
   nada tuyo). Clic en **Create repository**.
3. En la página del repositorio, clic en **uploading an existing file**.
4. Descomprime el zip y **arrastra TODO el contenido de la carpeta** `cazador-figuras`
   (incluida la carpeta `.github`) a la página. Clic en **Commit changes**.
   - Si la carpeta `.github` no se subió: **Add file → Create new file**, nombre
     `.github/workflows/cazador.yml`, y pega el contenido de ese archivo.

### 3. Dale tus claves secretas (2 min)

En el repositorio: **Settings → Secrets and variables → Actions → New repository secret**.
Crea dos:

| Name | Secret |
|---|---|
| `TELEGRAM_TOKEN` | el token del paso 1 |
| `TELEGRAM_CHAT_ID` | el número del paso 1 |

(Nadie más puede ver estos secretos, aunque el repositorio sea público.)

### 4. Enciéndelo y pruébalo (3 min)

1. Pestaña **Actions** → si pide permiso, clic en **I understand my workflows, go ahead and enable them**.
2. Clic en **Cazador de figuras** (izquierda) → **Run workflow** → en "modo" escribe `prueba` → **Run workflow**.
   En ~1 minuto te llega a Telegram: *"✅ ¡Funciona!"*.
3. Repite con modo `historico` (junta precios de ventas reales) y después con modo `normal`.
4. Listo: desde ahora corre solo cada 15 minutos.

### 5. Activa tu panel con fotos y gráficos (1 min)

**Settings → Pages** → *Source*: **Deploy from a branch** → Branch: **main** y carpeta **/docs** → **Save**.
En 1–2 minutos tu panel queda en:
`https://TU_USUARIO.github.io/cazador-figuras/`
Guárdalo en la pantalla de inicio del celular (Compartir → Agregar a inicio).

### 6. Ajusta Telegram para no perderte nada

En el chat de tu bot: toca el nombre → **Notificaciones** → elige un sonido propio y
**fíjalo arriba** (anclar chat). Las ofertas llegan con sonido; los listados nuevos
"normales" llegan en silencio para no molestarte.

---

## Qué alertas vas a recibir

| Alerta | Cuándo |
|---|---|
| 🚨🚨 **¡OFERTA BOMBA!** | ≥ 50 % más barata que el precio normal |
| 🔥 **OFERTA** | ≥ 30 % más barata |
| 💰 **DENTRO DE TU PRESUPUESTO** | igual o bajo el tope que tú pongas |
| 📉 **BAJÓ DE PRECIO** | un listado que ya era oferta bajó más |
| ⏰ **SUBASTA POR TERMINAR** | subasta barata a menos de 3 h de cerrar (cuando el sitio entrega la hora) |
| 🆕 Nuevo listado (silencioso) | cualquier listado nuevo de tus figuras prioritarias |
| 🆕 Caja o pieza suelta (con sonido) | cualquier caja vacía, cabeza, ropa, base o accesorio nuevo |
| 🛠 Fuente con problemas | un sitio falla varias veces seguidas, o su lector se rompió |
| 📋 Resumen diario (silencioso) | 9:23 AM: cuántos listados hay y si todo funciona |

Cada alerta trae foto, precio en yenes y en pesos, **costo estimado puesto en Chile**,
% vs. el precio normal, qué personaje es, si es subasta, si es *junk*/incompleta (⚠️)
o viene sin caja (📦❌), y links a **ZenMarket** y **Buyee** (Mercari y Yahoo).

---

### Junk, sin caja, cajas vacías y piezas sueltas
- Las figuras **junk, incompletas o sin caja** se tratan como la figura normal, marcadas ⚠️/📦❌.
- Las **cajas vacías y piezas sueltas** (cabezas, ropa, bases, accesorios) van a su propio
  artículo, *"Cajas vacías y piezas sueltas"*, para que una caja de ¥3.000 no parezca una
  "Homura escolar 90% más barata". Te avisa de todas las nuevas con sonido, y marca
  OFERTA si el total puesto en Chile cuesta menos que su tope (por defecto $60.000 CLP).
- Para el "precio normal" aprendido de ventas reales se usan solo figuras completas y en caja.

### Comparación justa entre países
El bot compara el **costo total puesto en Chile**, no solo el precio: a lo de Japón le suma
~¥9.000 (comisión ZenMarket + envío), a lo de China ~¥7.000 (Superbuy + envío), a eBay el
envío que dice el listado, y a MercadoLibre Chile nada. Así una figura en Chile a $190.000
puede ganarle a una "más barata" en Japón. Ajusta esos montos en `costo_hasta_chile_jpy`
(en `ajustes`) con lo que realmente te cobran; las piezas usan un envío menor.

## Cómo cambiar lo que busca (`config.yaml`)

En GitHub abre `config.yaml` → ícono del lápiz ✏️ → edita → **Commit changes**.
El próximo rastreo ya usa lo nuevo.

- **Poner un presupuesto:** en el artículo quita el `#` de la línea `presupuesto:` y
  cambia el monto. Moneda: `CLP`, `JPY` o `USD`.
  ```yaml
  presupuesto: {monto: 250000, moneda: CLP}
  ```
- **Cambiar qué es "barato":** `umbral_oferta: 0.30` (30 %) en `ajustes`, o por artículo.
- **Corregir el precio normal:** `precio_referencia_jpy`. El panel muestra el rango de
  ventas reales para que lo ajustes.
- **Solo buscar en Chile:** en el artículo agrega `paises: [CL]`
  (otros: `JP` para los sitios japoneses, `INT` para eBay).
- **Agregar cualquier otra cosa:** copia el bloque de ejemplo al final del archivo.
  O mejor: dile a Claude qué quieres buscar y te arma el bloque.

> Cuidado con los espacios: YAML usa la sangría (espacios al inicio) para entender la
> estructura. Copia el estilo de las líneas vecinas.

---

## Límites honestos

- **Goofish es experimental:** su web bloquea los servidores en la nube (como GitHub). El
  bot lo intenta igual; si al día siguiente te llega "🛠 Goofish: bloqueado", usa la sección
  de abajo para correrlo desde tu notebook.
- **Taobao** exige iniciar sesión siempre, así que no se puede rastrear sin tu cuenta.
- **Los sitios cambian su diseño.** Si uno deja de funcionar, recibes el aviso 🛠 y en el
  panel aparece en rojo. Pásale el mensaje de error a Claude para arreglarlo.
  Mercari usa su API, así que es el más estable.
- **GitHub a veces atrasa** la ejecución programada unos minutos en horas peak.
- Los precios no incluyen comisión del intermediario ni envío a Chile.
- Mercari solo muestra los ~120 listados más nuevos por búsqueda: perfecto para cazar
  lo recién publicado, que es justo lo que importa.

## Sitios desde el notebook (Goofish, Suruga-ya, Off Mall, Lashinbang, AmiAmi)

Estos sitios bloquean a los servidores en la nube, pero no a una conexión de casa. Funciona mientras el notebook
esté encendido:

1. Instala Python desde <https://www.python.org/downloads/> (marca **"Add python.exe to PATH"**).
2. Descomprime el zip en una carpeta fija, por ejemplo `Documentos\cazador-figuras`.
3. Copia `.env.ejemplo` como `.env` y pega tu `TELEGRAM_TOKEN` y `TELEGRAM_CHAT_ID`.
4. Doble clic en `notebook\instalar_tarea.bat` → queda programado cada 30 minutos.
5. Prueba ya: doble clic en `notebook\rastrear_notebook.bat` y revisa `notebook\registro.txt`.

Para mejorar aún más el éxito, inicia sesión en goofish.com en Chrome, copia tus cookies
(F12 → Application → Cookies) en una línea `nombre=valor; nombre=valor` y pégalas en
`GOOFISH_COOKIES` del archivo `.env`. Para quitarlo: `notebook\desinstalar_tarea.bat`.

## Diagnóstico diario

Cada mañana el bot busca algo genérico ("フィギュア", "figure", "手办"...) en cada sitio. Si un
sitio devuelve 0, su lector se rompió (el sitio cambió) y te llega un aviso 🛠 con el
detalle; en el panel aparece "lector roto". Mándale ese mensaje a Claude para arreglarlo.

## Correo (opcional)

Si además quieres las ofertas por email, crea estos secretos (ej. con Gmail y una
"contraseña de aplicación"): `SMTP_HOST` (`smtp.gmail.com`), `SMTP_PUERTO` (`587`),
`SMTP_USUARIO`, `SMTP_CLAVE`, `CORREO_DESTINO`.

## Archivos

```
config.yaml                 ← lo que buscas (lo único que normalmente editas)
cazador/                    ← el programa
  main.py                   ← orquesta todo y decide las alertas
  clasificador.py           ← reconoce qué figura es cada listado
  fuentes/                  ← un lector por sitio
docs/index.html             ← el panel web
docs/data.json              ← historial (lo escribe el bot solo)
notebook/                   ← scripts para correr Goofish desde Windows
.github/workflows/cazador.yml ← horario (cada 15 min + 1 vez al día)
tests/                      ← pruebas (python -m pytest)
```
