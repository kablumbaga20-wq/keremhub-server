from flask import Flask, jsonify, request, send_file, render_template_string
import os
import json
import zipfile
import hashlib
from io import BytesIO
from werkzeug.utils import secure_filename

app = Flask(__name__)

with open("config.json", "r", encoding="utf-8") as f:
    CONFIG = json.load(f)

PACKS_FOLDER = CONFIG.get("packs_folder", "/tmp/packs")
THUMBNAILS_FOLDER = CONFIG.get("thumbnail_folder", "/tmp/thumbnails")
BUILDER_FOLDER = CONFIG.get("builder_folder", "/tmp/builder")

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
    for file in os.listdir(PACKS_FOLDER):
        if not file.lower().endswith(".zip"):
            continue

        name = os.path.splitext(file)[0]

        if name.lower() == pack_id.lower():
            return os.path.join(PACKS_FOLDER, file)

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

    for file in z.namelist():
        lower = file.lower().replace("\\", "/")

        if lower.endswith("/"):
            continue

        for sword in sword_names:
            if lower.endswith("/" + sword) or lower == sword:
                found[sword] = file
                print("KILIC BULUNDU:", file)

    return found


@app.get("/health")
def health():
    return jsonify({
        "status": "ok"
    }), 200


@app.route("/")
def home():
    return jsonify({
        "name": CONFIG["server_name"],
        "packs_folder": PACKS_FOLDER,
        "status": "online"
    })


@app.route("/upload", methods=["GET", "POST"])
def upload_pack():
    if request.method == "POST":
        file = request.files.get("file")

        if not file or not file.filename:
            return "Dosya seçilmedi", 400

        if not file.filename.lower().endswith(".zip"):
            return "Sadece ZIP yüklenebilir", 400

        filename = secure_filename(file.filename)

        if not filename:
            return "Geçersiz dosya adı", 400

        path = os.path.join(PACKS_FOLDER, filename)

        file.save(path)

        return render_template_string("""
        <!DOCTYPE html>
        <html lang="tr">
        <head>
            <meta charset="UTF-8">
            <title>KeremHub</title>
        </head>
        <body>
            <h1>Pack yüklendi!</h1>
            <p>{{ filename }}</p>
            <a href="/upload">Başka pack yükle</a>
            <br>
            <a href="/api/packs">Pack listesini aç</a>
        </body>
        </html>
        """, filename=filename)

    return render_template_string("""
    <!DOCTYPE html>
    <html lang="tr">
    <head>
        <meta charset="UTF-8">
        <title>KeremHub Pack Upload</title>
    </head>
    <body>
        <h1>KeremHub Pack Yükle</h1>

        <form method="POST" enctype="multipart/form-data">
            <input
                type="file"
                name="file"
                accept=".zip"
                required
            >

            <button type="submit">
                Pack Yükle
            </button>
        </form>
    </body>
    </html>
    """)


@app.route("/api/packs")
def api_packs():
    packs = []

    for file in os.listdir(PACKS_FOLDER):
        if not file.lower().endswith(".zip"):
            continue

        path = os.path.join(PACKS_FOLDER, file)
        name = os.path.splitext(file)[0]

        packs.append({
            "id": name,
            "name": name,
            "pack_filename": file,
            "author_name": CONFIG["author"],
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

    print("Toplam pack:", len(packs))

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

    file = os.path.basename(path)
    name = os.path.splitext(file)[0]

    return jsonify({
        "id": name,
        "name": name,
        "pack_filename": file,
        "author_name": CONFIG["author"],
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
            for file in z.namelist():
                if file.lower().endswith("pack.png"):
                    return send_file(
                        BytesIO(z.read(file)),
                        mimetype="image/png"
                    )

    except Exception as e:
        print("THUMBNAIL ERROR:", e)

    return "No Thumbnail", 404


if __name__ == "__main__":
    app.run(
        host=CONFIG.get("host", "0.0.0.0"),
        port=int(os.environ.get("PORT", CONFIG.get("port", 8000)))
    )
