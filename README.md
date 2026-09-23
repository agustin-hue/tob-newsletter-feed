# Feed RSS del newsletter: guía paso a paso

## Qué vas a tener al final

Una URL tipo `https://tu-usuario.github.io/tob-newsletter-feed/feed.xml` con **todos** los issues: los viejos de listmonk y los nuevos de Mailmodo, ordenados por fecha y limpios para web (sin pixel de tracking, sin links de baja, con los links reales). El cliente conecta esa URL a su página y los issues le aparecen solos.

Cada issue nuevo se agrega **subiendo un archivo**. Sin terminal, sin programar. GitHub arma y publica el feed automáticamente.

Costo: $0 (GitHub gratis).

---

## PARTE 1: Configuración inicial (una sola vez, ~30 min)

### Paso 1. Crear cuenta en GitHub
Entrá a https://github.com y creá una cuenta. Si ya tenés, usala. Si es para el cliente, lo ideal es una cuenta o organización de OPTIN, no personal.

### Paso 2. Crear el repositorio
1. Arriba a la derecha: **+** > **New repository**.
2. Nombre: `tob-newsletter-feed` (tiene que ser exacto: la URL del feed depende de este nombre).
3. Marcá **Public**. GitHub Pages gratis necesita repo público. No hay problema: el contenido es un archivo público de newsletter.
4. **No** marques "Add a README". Click **Create repository**.

### Paso 3. Subir los archivos
1. Descomprimí el `.zip` en tu computadora.
2. En la página del repo nuevo, click en el link **uploading an existing file**.
3. Arrastrá **todo el contenido** de la carpeta descomprimida (no la carpeta en sí, lo que hay adentro).
4. Abajo, click **Commit changes**.

> **Ojo con la carpeta `.github`.** Empieza con punto y en Mac/Windows suele estar oculta, así que es fácil que no se suba.
> Para verificar: en el repo tiene que aparecer una carpeta `.github`. Si no aparece:
> 1. Click **Add file** > **Create new file**.
> 2. En el nombre escribí exactamente: `.github/workflows/build.yml`
> 3. Pegá adentro el contenido del archivo `build.yml` del zip (abrilo con el Bloc de notas).
> 4. **Commit changes**.

### Paso 4. Activar GitHub Pages
1. En el repo: **Settings** (arriba) > **Pages** (menú izquierdo).
2. En **Source** elegí **GitHub Actions**.

### Paso 5. Editar `config.json`
1. Click en `config.json` > ícono del lápiz (Edit).
2. Cambiá `TU-USUARIO` por tu usuario de GitHub en `site_url`. Ejemplo: `"https://optin-media.github.io/tob-newsletter-feed"`.
3. Revisá `title` y `description`: es lo que va a ver el cliente como nombre del feed.
4. **Commit changes**.

### Paso 6. Guardar la copia de los issues de listmonk
Así el feed no depende de que listmonk siga funcionando.
1. Abrí en el navegador: https://150.colonysparkweekly.com/archive.xml
2. **Ctrl+S** (Mac: **Cmd+S**) y guardalo con el nombre exacto `listmonk_archive.xml`.
3. En el repo: **Add file** > **Upload files** > subilo > **Commit changes**.

> Verificá que estén todos los issues viejos: abrí el archivo y contá los `<item>`. Si faltan los más antiguos, listmonk está limitando cuántos muestra el feed. En ese caso avisame y lo resolvemos.

### Paso 7. Averiguar el dominio de tracking de Mailmodo
Para que el script reemplace los links de tracking por los reales, tiene que saber cómo se ven.
1. Abrí en Gmail cualquier issue que haya salido por Mailmodo.
2. Pasá el mouse por arriba de un link (sin hacer click) y mirá abajo a la izquierda la URL que aparece.
3. Anotá el dominio, que es lo que va entre `https://` y la siguiente `/`.
4. En `config.json`, agregalo a la lista `tracking_hosts`:
   ```json
   "tracking_hosts": ["150.colonysparkweekly.com", "EL-DOMINIO-QUE-ANOTASTE"],
   ```

---

## PARTE 2: Agregar issues de Mailmodo (cada vez que sale uno, ~2 min)

### Opción A: archivo .eml (recomendada, la más fácil)
1. En Gmail, abrí el issue que recibiste (en una casilla tuya suscripta a la lista).
2. Menú **⋮** (arriba a la derecha del mail) > **Descargar mensaje**. Se baja un `.eml`.
3. En el repo, entrá a la carpeta `issues/` > **Add file** > **Upload files** > subí el `.eml` > **Commit changes**.

Listo. El título y la fecha se leen solos del mail.

> **Importante:** la casilla que uses tiene que estar suscripta **sin nombre** (o con nombre vacío). Si no, el "Hi Agus" del saludo personalizado queda publicado en la web del cliente.

### Opción B: archivo .html
Si tenés el HTML en vez del mail:
1. Nombralo empezando con la fecha: `2026-07-16-issue-19.html`.
2. Subilo a `issues/`.
3. Editá `issues.csv` y agregá una línea con el título:
   ```
   archivo,titulo,fecha
   2026-07-16-issue-19.html,Título real del issue,2026-07-16
   ```

`issues.csv` también sirve para **corregir** título o fecha de cualquier issue, incluidos los `.eml`: poné el nombre del archivo y el dato correcto.

---

## PARTE 3: Verificar que funcionó

1. En el repo, pestaña **Actions**. Cada vez que subís algo arranca un proceso.
   - Círculo amarillo: está trabajando (1-2 min).
   - Tilde verde: salió bien.
   - Cruz roja: algo falló (ver Problemas comunes).
2. Abrí tu `site_url` + `/feed.xml`. Ejemplo: `https://optin-media.github.io/tob-newsletter-feed/feed.xml`
3. Abrí tu `site_url` a secas: vas a ver un listado con todos los issues, cada uno clickeable.
4. Validá el feed en https://validator.w3.org/feed/ pegando la URL.
5. **Revisá los avisos**: en Actions, click en el último proceso > **build** > paso **Run python build_feed.py**. Si dice `AVISO`, leelo. Por ejemplo, "merge tags sin reemplazar" significa que había un `{{nombre}}` que se borró y conviene revisar cómo quedó ese saludo.

Cuando esté todo verde, **pasale al cliente la URL del feed.xml**.

---

## Qué le tenés que decir al cliente

- **URL del feed:** la de `feed.xml`.
- **El contenido completo de cada issue** viene en el campo `content:encoded`, como HTML listo para insertar (solo el cuerpo del mail, sin `<html>` ni `<head>`).
- **El resumen corto** viene en `description`.
- **Si su importador necesita el mail completo** (por ejemplo, para mostrarlo en un iframe), que use el `link` de cada item: apunta a la página con el issue entero.
- **Los `guid` no cambian**, así que su sistema no va a duplicar issues.

---

## Problemas comunes

**Cruz roja en Actions**
Click en el proceso rojo > buscá la línea en rojo. Casos típicos:
- `config.json` con un error de formato: falta una coma o sobra una. Pegalo en https://jsonlint.com para ver dónde.
- Pages no activado: repetí el Paso 4.

**El feed no muestra un issue que subí**
Mirá los avisos (Parte 3, punto 5). Seguramente dice "falta título o fecha": agregalo en `issues.csv`.

**Un link sigue apuntando al tracking**
No agregaste ese dominio en `tracking_hosts` (Paso 7). Agregalo y subí cualquier cambio para que se rearme el feed. También podés ir a **Actions** > **Armar y publicar feed** > **Run workflow**.

**Editaste `issues.csv` en Excel y quedó raro**
Mejor editalo directo en GitHub (lápiz). Si usás Excel, guardalo como "CSV UTF-8".

**Quiero cambiar la fecha de un issue**
Poné una línea en `issues.csv` con la fecha correcta. Ojo: cambiar la fecha cambia la URL de su página.

---

## Qué hace cada archivo (por si lo necesitás)

| Archivo | Para qué |
|---|---|
| `build_feed.py` | El script que arma el feed. No hace falta tocarlo. |
| `config.json` | Configuración: URL, título, dominios de tracking, qué borrar. |
| `issues/` | Acá van los issues de Mailmodo (`.eml` o `.html`). |
| `issues.csv` | Opcional: títulos y fechas manuales o correcciones. |
| `listmonk_archive.xml` | Copia congelada de los issues viejos. |
| `.github/workflows/build.yml` | Le dice a GitHub que arme y publique el feed en cada cambio. |
| `requirements.txt` | Librerías que usa el script. |

**Qué limpia el script en cada issue:**
- el pixel de tracking, para que las visitas a la web no cuenten como opens
- el preheader oculto
- los links de baja, preferencias y "ver en el navegador"
- el texto "You're receiving this because..."
- los merge tags sin reemplazar

Además reemplaza los links de tracking por la URL real. Para esto sigue cada link una sola vez: puede sumar 1 click por link en las métricas, pero solo la primera vez. Los links de baja se borran antes, así que nunca se "clickean".
