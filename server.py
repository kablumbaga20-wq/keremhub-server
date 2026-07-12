from flask import Flask, jsonify, request, send_file, render_template_string
import os
import json
import zipfile
import hashlib
from io import BytesIO
from werkzeug.utils import secure_filename

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

with open(os.path.join(BASE_DIR, "config.json"), "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

PACKS_FOLDER = os.path.join(BASE_DIR, CONFIG.get("packs_folder", "packs"))
THUMBNAILS_FOLDER = os.path.join(BASE_DIR, CONFIG.get("thumbnail_folder", "thumbnails"))
BUILDER_FOLDER = os.path.join(BASE_DIR, CONFIG.get("builder_folder", "builder"))

os.makedirs(PACKS_FOLDER, exist_ok=True)
os.makedirs(THUMBNAILS_FOLDER, exist_ok=True)
os.makedirs(BUILDER_FOLDER, exist_ok=True)


def sha256_file(path):
    h = hashlib.sha256()

    with open(path, "rb") as f:
        while True:
            chunk = f.read(8192)

            if not chunk:
                break

            h.update(chunk)

    return h.hexdigest()


def find_zip(pack_id):
    for filename in os.listdir(PACKS_FOLDER):
        if not filename.lower().endswith(".zip"):
            continue

        name = os.path.splitext(filename)[0]

        if name.lower() == pack_id.lower():
            return os.path.join(PACKS_FOLDER, filename)

    return None


def find_swords(z):
    sword_names = [
        "wooden_sword.png",
        "wood_sword.png",
        "stone_sword.png",
        "iron_sword.png",
        "golden_sword.png",
        "gold_sword.png",
        "diamond_sword.png",
        "netherite_sword.png"
    ]

    found = {}

    for filename in z.namelist():
        lower = filename.lower().replace("\\", "/")

        if lower.endswith("/"):
            continue

        for sword in sword_names:
            if lower.endswith("/" + sword) or lower == sword:
                found[sword] = filename

    return found


@app.get("/health")
def health():
    return jsonify({
        "status": "ok"
    }), 200


@app.get("/")
def home():
    return jsonify({
        "name": CONFIG.get("server_name", "KeremHub"),
        "packs_folder": PACKS_FOLDER,
        "status": "online"
    })


@app.route("/upload", methods=["GET", "POST"])
def upload_pack():
    if request.method == "POST":
        files = request.files.getlist("files")

        uploaded = []
        skipped = []

        for file in files:
            if not file or not file.filename:
                continue

            original_name = file.filename.replace("\\", "/")

            if not original_name.lower().endswith(".zip"):
                continue

            filename = secure_filename(
                os.path.basename(original_name)
            )

            if not filename:
                skipped.append(original_name)
                continue

            path = os.path.join(PACKS_FOLDER, filename)

            try:
                file.save(path)

                if not zipfile.is_zipfile(path):
                    os.remove(path)
                    skipped.append(original_name)
                    continue

                uploaded.append(filename)

            except Exception as e:
                print("UPLOAD ERROR:", original_name, e)

                if os.path.exists(path):
                    try:
                        os.remove(path)
                    except Exception:
                        pass

                skipped.append(original_name)

        return render_template_string("""
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>KeremHub</title>
</head>
<body>

<h1>Yükleme tamamlandı</h1>

<h2>{{ count }} pack yüklendi.</h2>

{% if skipped %}
<h3>Atlanan dosyalar:</h3>

{% for filename in skipped %}
<p>{{ filename }}</p>
{% endfor %}

{% endif %}

<br>

<a href="/upload">Başka klasör yükle</a>

<br><br>

<a href="/api/packs">Pack listesini aç</a>

</body>
</html>
""", count=len(uploaded), skipped=skipped)

    return render_template_string("""
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">

    <title>KeremHub Pack Upload</title>
</head>

<body>

<h1>KeremHub Pack Yükle</h1>

<p>Pack klasörünü seç.</p>

<p>Klasördeki tüm ZIP dosyaları otomatik yüklenecek.</p>

<form
    method="POST"
    enctype="multipart/form-data"
>

<input
    type="file"
    name="files"
    webkitdirectory
    directory
    multiple
    required
>

<br><br>

<button type="submit">
    Klasördeki Packleri Yükle
</button>

</form>

</body>
</html>
""")


@app.get("/api/packs")
def api_packs():
    packs = []

    for filename in os.listdir(PACKS_FOLDER):
        if not filename.lower().endswith(".zip"):
            continue

        path = os.path.join(PACKS_FOLDER, filename)
        name = os.path.splitext(filename)[0]

        packs.append({
            "id": name,
            "name": name,
            "pack_filename": filename,
            "author_name": CONFIG.get("author", "Kerem"),
            "author_id": "local",
            "showcase_path": f"/thumbnails/{name}.png",
            "pack_url": f"/api/packs/{name}/pack",
            "tag": "PvP",
            "tags": ["PvP"],
            "downloads": 0,
            "star_count": 0,
            "viewer_starred": False,
            "is_zip": True,
            "has_local_file": True,
            "approved_at": 0,
            "sha256": sha256_file(path)
        })

    return jsonify(packs)


@app.get("/api/packs/<pack_id>/pack")
def download_pack(pack_id):
    path = find_zip(pack_id)

    if path is None:
        return "Pack not found", 404

    return send_file(
        path,
        as_attachment=True
    )


@app.post("/api/packs/request")
def pack_request():
    data = request.get_json(silent=True) or {}

    pack_id = (
        data.get("id")
        or data.get("pack_id")
        or data.get("packId")
    )

    if not pack_id:
        return jsonify({
            "error": "missing id"
        }), 400

    path = find_zip(pack_id)

    if path is None:
        return jsonify({
            "error": "not found"
        }), 404

    filename = os.path.basename(path)
    name = os.path.splitext(filename)[0]

    return jsonify({
        "id": name,
        "name": name,
        "pack_filename": filename,
        "author_name": CONFIG.get("author", "Kerem"),
        "author_id": "local",
        "showcase_path": f"/thumbnails/{name}.png",
        "pack_url": f"/api/packs/{name}/pack",
        "tag": "PvP",
        "tags": ["PvP"],
        "downloads": 0,
        "star_count": 0,
        "viewer_starred": False,
        "is_zip": True,
        "has_local_file": True,
        "approved_at": 0,
        "sha256": sha256_file(path)
    })


@app.get("/api/packs/<pack_id>/sword")
def sword_preview(pack_id):
    path = find_zip(pack_id)

    if path is None:
        return "Pack not found", 404

    try:
        with zipfile.ZipFile(path, "r") as z:
            swords = find_swords(z)

            preview_order = [
                "diamond_sword.png",
                "netherite_sword.png",
                "iron_sword.png",
                "golden_sword.png",
                "gold_sword.png",
                "stone_sword.png",
                "wooden_sword.png",
                "wood_sword.png"
            ]

            for sword in preview_order:
                if sword in swords:
                    return send_file(
                        BytesIO(z.read(swords[sword])),
                        mimetype="image/png"
                    )

    except Exception as e:
        print("SWORD ERROR:", e)
        return "Sword error", 500

    return "Sword not found", 404


@app.get("/api/packs/<pack_id>/swords-pack")
def swords_pack(pack_id):
    path = find_zip(pack_id)

    if path is None:
        return "Pack not found", 404

    output = BytesIO()

    try:
        with zipfile.ZipFile(path, "r") as source:
            swords = find_swords(source)

            if not swords:
                return "Sword not found", 404

            with zipfile.ZipFile(
                output,
                "w",
                zipfile.ZIP_DEFLATED
            ) as target:

                pack_mcmeta = {
                    "pack": {
                        "pack_format": 15,
                        "description": "KeremHub Sword Pack"
                    }
                }

                target.writestr(
                    "pack.mcmeta",
                    json.dumps(pack_mcmeta)
                )

                name_map = {
                    "wood_sword.png": "wooden_sword.png",
                    "gold_sword.png": "golden_sword.png"
                }

                for sword, source_file in swords.items():
                    output_name = name_map.get(
                        sword,
                        sword
                    )

                    target.writestr(
                        "assets/minecraft/textures/item/" + output_name,
                        source.read(source_file)
                    )

    except Exception as e:
        print("SWORDS PACK ERROR:", e)
        return "Pack build error", 500

    output.seek(0)

    safe_name = "".join(
        c if c.isalnum() or c in "._-" else "_"
        for c in pack_id
    )

    return send_file(
        output,
        mimetype="application/zip",
        as_attachment=True,
        download_name=f"KeremHub-{safe_name}.zip"
    )


@app.get("/thumbnails/<path:name>.png")
def thumbnail(name):
    path = find_zip(name)

    if path is None:
        return "Not Found", 404

    try:
        with zipfile.ZipFile(path, "r") as z:
            for filename in z.namelist():
                if filename.lower().endswith("pack.png"):
                    return send_file(
                        BytesIO(z.read(filename)),
                        mimetype="image/png"
                    )

    except Exception as e:
        print("THUMBNAIL ERROR:", e)

    return "No Thumbnail", 404


if __name__ == "__main__":
    app.run(
        host=CONFIG.get("host", "0.0.0.0"),
        port=int(
            os.environ.get(
                "PORT",
                CONFIG.get("port", 8000)
            )
        )
    )
