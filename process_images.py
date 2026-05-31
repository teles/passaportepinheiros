#!/usr/bin/env python3
"""
Process Passaporte Pinheiros Instagram cards into Astro Content-friendly folders.

For each source image in data/instagram/{produtos,restaurantes,servicos}:
- write src/content/experiencias/{category}/{slug}.md
- create public/experiencias/{category}/{slug}/
- crop the top experience photo to public assets as experiencia.jpg
- crop the company logo to public assets as logo.png

The current Instagram card set has a curated metadata table below. For new cards,
the script falls back to local OCR with Tesseract.
"""

from __future__ import annotations

import argparse
import csv
import io
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).parent
INSTAGRAM_DIR = BASE_DIR / "data" / "instagram"
CONTENT_DIR = BASE_DIR / "src" / "content" / "experiencias"
PUBLIC_ASSETS_DIR = BASE_DIR / "public" / "experiencias"
PUBLIC_ASSETS_URL = "/experiencias"
CATEGORIES = ("produtos", "restaurantes", "servicos")

PHOTO_HEIGHT_RATIO = 608 / 1920
LOGO_BG = "#fbfaf6"


@dataclass(frozen=True)
class CardInfo:
    title: str
    description: str
    instagram: str


KNOWN_CARDS: dict[str, CardInfo] = {
    "684272246_18107582729304897_2538628061660273634_n..webp": CardInfo(
        "Blanche Brasil",
        """Na compra de 1 óculos,
ganhe outro dentre as peças
selecionadas na promoção do
Passaporte Pinheiros""",
        "blanche.brasil",
    ),
    "684221894_18107582819304897_7249970102794367123_n..webp": CardInfo(
        "Balcone",
        """Na compra de um prato*
seu acompanhante ganha outro de
igual ou menor valor.
*Exceto o prato Polvo Grelhado.""",
        "balcone.sp",
    ),
    "684237932_18107532797304897_3147131184310313914_n..webp": CardInfo(
        "Miya Wine Bar",
        """Na compra de 1 entrada,
ganhe outra de igual ou menor
valor.""",
        "miyawinebar",
    ),
    "684263169_18107532989304897_7154819012744215479_n..webp": CardInfo(
        "Emporio São João",
        """Na compra de 1 nhoque artesanal
de batatas ao molho de ragu de
carne assada, seu
acompanhante ganha outro
igual.""",
        "emporiosaojoao",
    ),
    "684275118_18107686445304897_6736158086641761042_n..webp": CardInfo(
        "O Pasquim",
        """Na compra de um petisco
e um drink
seu acompanhante ganha
outro petisco e outro drink
de igual ou menor valor.
*Válido de segunda a
sexta-feira.""",
        "opasquimbar",
    ),
    "684281085_18107582714304897_1053894189868637870_n..webp": CardInfo(
        "Braz Trattoria",
        """Na compra de 1 prato,
ganhe 1 taça de vinho Braz.
*Válido somente no restaurante da
Rua dos Pinheiros, de segunda a
quinta-feira.""",
        "braztrattoria",
    ),
    "684302753_18107653589304897_4439106225119108146_n..webp": CardInfo(
        "Toscana Focacceria",
        """Na compra de qualquer
item do cardápio,
seu acompanhante ganha
50% de desconto no item
escolhido de igual ou
menor valor""",
        "toscana.focacceria",
    ),
    "684351895_18107653265304897_521418019643609772_n..webp": CardInfo(
        "Lanchonete da Cidade",
        """Na compra de 1 burguer ou
sanduíche, seu acompanhante
ganha outro de igual ou menor
valor.
*Válido na Lanchonete da
Cidade de Pinheiros""",
        "lanchonetedacidade",
    ),
    "684358399_18107582684304897_9171869787164451850_n..webp": CardInfo(
        "Feliciana Pães",
        """Na compra de 1 bebida quente + 1
pão na chapa seu
acompanhante ganha outra
bebida quente + 1 pão na chapa
de igual ou menor valor.
*Válido de segunda a sexta-feira.""",
        "feliciana.paes",
    ),
    "684391011_18107653313304897_7121303415902274826_n..webp": CardInfo(
        "Beer4u",
        """1º Carimbo:
Na compra de 1 pint de chope da casa + 1
petisco (empanada ou espetinho), ganhe
outro pint de chope da casa de igual ou
menor valor e outro petisco de igual ou
menor valor.
2º carimbo:
Na compra de um pint de cervejaria
convidada + 1 petisco, ganhe 1 copo de
500 ml da Pilsen ou Ipa da casa.""",
        "beer4upinheiros",
    ),
    "684433741_18107532878304897_3062667008071127746_n..webp": CardInfo(
        "La Sabrosa",
        """Na compra de 1 taco,
ganhe outro de igual ou menor
valor.""",
        "taquerialasabrosa",
    ),
    "684506231_18107686316304897_7941550905378918750_n..webp": CardInfo(
        "Pirajá",
        """Na compra de um chopp + uma porção
da sessão "bolinhos"*, seu acompanhante
ganha outro chopp
e outro bolinho de igual ou menor valor.
*Com exceção do bolinho de bacalhau e
cupinzeiro.
*Válido nas unidades de Pinheiros,
Eldorado ou Villa Lobos, somente no
Happy Hour das 17h até às 20h.""",
        "barpiraja",
    ),
    "684551696_18107695847304897_1610803269986908375_n..webp": CardInfo(
        "Nour",
        """Na compra de 1 prato,
seu acompanhante ganha 50%
de desconto no segundo prato.
*Exceto Kafta de Cordeiro e Filé
Mignon.
*Válido somente aos sábados""",
        "nourbrasil",
    ),
    "684585222_18107533154304897_7504348542463716753_n..webp": CardInfo(
        "Capivara",
        """Na compra de um 1 lanche ou 1
porção, seu acompanhante ganha
outro lanche ou outra porção de
igual ou menor valor.""",
        "redecapivara",
    ),
    "684607858_18107532911304897_120946300452091460_n..webp": CardInfo(
        "GUA.CO",
        """Na compra de 1 prato principal,
ganhe um taco.""",
        "gua.co",
    ),
    "684620935_18107533070304897_1974193859578041160_n..webp": CardInfo(
        "Dedo de La Chica",
        """Na compra de 1 rodízio
mexicano seu acompanhante
ganha 50% de desconto no
segundo rodízio.""",
        "dedodelachica",
    ),
    "684762217_18107532764304897_5243164425353511701_n..webp": CardInfo(
        "Al Mazen",
        """Na compra de um rodízio
completo ganhe 50% de
desconto na compra do rodízio
completo do seu acompanhante.""",
        "almazen_chefmazenzwawe",
    ),
    "684762221_18107533028304897_499562404416732035_n..webp": CardInfo(
        "Dona Vitamina",
        """Na compra de 1 sanduíche de
frango desfiado no pão folha,
seu acompanhante ganha
outro igual.""",
        "donavitamina",
    ),
    "684812735_18107532818304897_8265484282910086032_n..webp": CardInfo(
        "Manduque Massas e Maçãs",
        """Na compra de qualquer prato, leve
para casa nossa deliciosa massa
caseira sem recheio de 200g.""",
        "manduque.massas",
    ),
    "684831002_18107533127304897_6298949641024748270_n..webp": CardInfo(
        "Carmel's Pipocas",
        """Na compra de 1 pote de Caramelo
com Flor de Sal, ganhe outro de
igual ou menor valor.""",
        "carmelspipocas",
    ),
    "685723285_18107686235304897_3936802905578385527_n..webp": CardInfo(
        "Sakeumi Restaurante",
        """Na compra de 1 Rodízio TRADICIONAL
ganhe 50% de desconto no Rodízio
TRADICIONAL do seu acompanhante.
*Válido apenas no rodízio tradicional,
no jantar, de segunda a quinta feira
*Não é válido em feriado e datas
comemorativas.""",
        "sakeumi.restaurante",
    ),
    "685789872_18107686421304897_4224829060856598659_n..webp": CardInfo(
        "Ombra",
        """Na compra de 1 pedaço de
pizza, seu acompanhante
ganha outro pedaço de pizza.
OU
Na compra de 1 taça de vinho,
seu acompanhante ganha
outra taça de vinho.""",
        "ombra_sp",
    ),
    "685914583_18107653667304897_6376612293793662530_n..webp": CardInfo(
        "The Taco Shop",
        """Na compra de um prato, ganhe
outro de igual ou menor valor.""",
        "thetacoshop_br",
    ),
    "686168952_18107686214304897_8284574910715016662_n..webp": CardInfo(
        "Suri",
        """Primeira visita:
na compra de 1 drink ou refresco,
seu acompanhante ganha outro
de igual ou menor valor.
Segunda visita:
na compra de 1 ceviche, seu
acompanhante ganha outro de
igual ou menor valor.""",
        "suricevichebar",
    ),
    "686319292_18107582549304897_4286890208299419828_n..webp": CardInfo(
        "Coffe Walk",
        """Primeiro Carimbo:
50% de desconto em qualquer
produto.
Segundo carimbo:
Na compra de um produto você
ganha outro produto de igual ou
menor valor.""",
        "coffeewalkbr",
    ),
    "686331001_18107686250304897_3574150192523446794_n..webp": CardInfo(
        "Ripito",
        """Na compra de 1 Prato
Principal (ou do dia)
seu acompanhante ganha 1
fatia de Torta com Salada.""",
        "ripito.cafeteria",
    ),
    "686344361_18107695886304897_1510785856816467132_n..webp": CardInfo(
        "NOS outros",
        """Na compra de 1 item* do
cardápio, seu acompanhante
ganha outro de igual ou menor
valor.
*Tapas e Montaditos
*Válido de terça a sexta-feira
em qualquer horário e sábado
das 12h às 19h.""",
        "nos.otros",
    ),
    "686367932_18107653253304897_6232399824314841584_n..webp": CardInfo(
        "Low BBQ",
        """Na compra de 1 prato
individual ou sanduíche,
seu acompanhante ganha
outro prato individual ou
sanduíche de igual ou menor
valor.
*Válido de segunda a sexta""",
        "lowbbqbar",
    ),
    "686425276_18107685992304897_211750122792936024_n..webp": CardInfo(
        "Taba Pastéis e Salgados",
        """No primeiro carimbo:
compre 1 pastel e ganhe outro pastel de
qualquer sabor*.
No segundo carimbo:
compre 1 pastel* + 1 garrafa de 500ml de
caldo de cana e seu acompanhante
ganha outro pastel* + 1 garrafa de
500ml de caldo de cana.
*Exceto sabores especiais.""",
        "tabapasteis",
    ),
    "686466601_18107653433304897_2816366475888946094_n..webp": CardInfo(
        "Bakebun Bakery",
        """Na compra de 1 Cinnamon Roll
Cobertura Especial seu
acompanhante ganha outro
Cinnamon Roll Cobertura Especial.""",
        "bakebunoficial",
    ),
    "687169360_18107582702304897_4316215101597420399_n..webp": CardInfo(
        "C do Padre",
        """Na compra de 1 prato, seu
acompanhante ganha outro de igual
ou menor valor.
*Válido apenas no horário do almoço.
Após às 14h30, na compra de qualquer
lanche ou porção, seu acompanhante
ganha outro de igual ou menor valor.""",
        "ocdopadre",
    ),
    "687523008_18107582762304897_6649100160283709191_n..webp": CardInfo(
        "Bar do Quintal",
        """Aos Sábados e Domingos, na
compra de 1 Buffet de Feijoada à
vontade, seu acompanhante
ganha outro Buffet de Feijoada.""",
        "bardoquintal",
    ),
    "687684471_18107686358304897_7428499089525854654_n..webp": CardInfo(
        "Petros Greek Taverna",
        """Na compra de uma jarra de
Clericot, ganhe outra.
OU
Na compra de 1 Moussaka
tradicional, seu acompanhante
ganha 50% de desconto na
segunda Moussaka tradicional.""",
        "petrosgreektaverna",
    ),
    "687686958_18107653511304897_5129309674380833100_n..webp": CardInfo(
        "Vino!",
        """Na compra de 1 prato do
cardápio, seu
acompanhante tem 50% de
desconto no segundo prato
de igual ou menor valor.""",
        "vinopinheiros",
    ),
    "687801291_18107582744304897_443903714475058698_n..webp": CardInfo(
        "Beik Cookies",
        """Na compra de 1 cookie e um café,
ganhe outro cookie e outro café de
igual ou menor valor.""",
        "beik_cookies",
    ),
    "688761688_18107653544304897_5460981802516203332_n..webp": CardInfo(
        "Trinca Bar",
        """Na compra de 1 vermute artesanal
+ 1 entrada, seu acompanhante
ganha outro vermute e outra
entrada de igual ou menor valor.
*Válido de Terça a Sexta-feira.
*Não é valido para as vésperas e
dias de feriado.""",
        "trincabar",
    ),
    "689207448_18107686397304897_4616318609163430430_n..webp": CardInfo(
        "Panda Ya",
        """Na compra de 1 porção de
Gyoza ganhe outra porção de
Gyoza de igual ou menor valor.
*Válido somente na unidade
da Rua Lisboa, 971.""",
        "pandaya.dumpling",
    ),
    "689455568_18107686286304897_6584300782887316755_n..webp": CardInfo(
        "Rendez Vous",
        """Na compra de 1 prato principal à la
carte, seu acompanhante ganha
outro de igual ou menor valor.
*Exceto Beouf Wellington
*Válido somente no jantar, de
Segunda à Sexta-feira, das 19h às
22h30.""",
        "rendezvous.bistro",
    ),
    "694283467_18107582660304897_7971929137062943954_n..webp": CardInfo(
        "HM Food Café",
        """Na compra de 1 prato, seu
acompanhante ganha outro
de igual ou menor valor.
*Válido somente no almoço de
segunda a sexta""",
        "hmfoodcafe",
    ),
    "694461037_18107653469304897_7524314637509775171_n..webp": CardInfo(
        "Albero Dei Gelati",
        """Compre 1 gelato
pequeno, médio ou grande e seu
acompanhante ganha outro do
mesmo tamanho.""",
        "alberodeigelati",
    ),
    "685894226_18107695934304897_8716529358017958955_n..webp": CardInfo(
        "Modern Pets",
        """Desconto de R$ 75,00 para
novas assinaturas
da Clínica Veterinária Modern
Pets.
O mesmo será aplicado
parcialmente ao longo do
período de 12 meses.""",
        "modernpets.br",
    ),
    "686225003_18107695829304897_7894720944075881833_n..webp": CardInfo(
        "Ogres Tatoo",
        """20% de desconto em
qualquer tattoo e piercing.""",
        "ogrestattoo",
    ),
    "686396333_18107582633304897_5352370658744856420_n..webp": CardInfo(
        "InFlux",
        """Isenção da taxa de matricula""",
        "influxbr",
    ),
}


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text.lower().strip())
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def require_command(command: str) -> None:
    if shutil.which(command):
        return
    raise RuntimeError(f"Required command not found: {command}")


def run_command(args: list[str]) -> str:
    result = subprocess.run(args, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if result.returncode != 0:
        raise RuntimeError(
            f"Command failed ({result.returncode}): {' '.join(args)}\n{result.stderr.strip()}"
        )
    return result.stdout


def image_size(path: Path) -> tuple[int, int]:
    raw = run_command(["magick", "identify", "-format", "%w %h", str(path)]).strip()
    width, height = raw.split()
    return int(width), int(height)


def crop_experience_photo(image_path: Path, out_path: Path) -> None:
    width, height = image_size(image_path)
    photo_height = round(height * PHOTO_HEIGHT_RATIO)
    run_command(
        [
            "magick",
            str(image_path),
            "-crop",
            f"{width}x{photo_height}+0+0",
            "-quality",
            "92",
            str(out_path),
        ]
    )


def crop_logo(image_path: Path, out_path: Path) -> None:
    width, height = image_size(image_path)
    photo_height = round(height * PHOTO_HEIGHT_RATIO)
    crop_width = round(width * 0.56)
    crop_x = round((width - crop_width) / 2)
    crop_y = photo_height + round(height * 0.022)
    crop_height = round(height * 0.104)

    run_command(
        [
            "magick",
            str(image_path),
            "-crop",
            f"{crop_width}x{crop_height}+{crop_x}+{crop_y}",
            "-fuzz",
            "9%",
            "-trim",
            "+repage",
            "-bordercolor",
            LOGO_BG,
            "-border",
            "24",
            str(out_path),
        ]
    )


def clean_instagram(raw: str) -> str:
    raw = raw.strip().replace(" ", "").replace(",", ".")
    raw = raw.lstrip("@")
    if raw and raw[0] in {"G", "6", "Q"}:
        raw = raw[1:]
    raw = re.sub(r"[^A-Za-z0-9_.]", "", raw)
    return raw.lower().strip("._")


def ocr_file(path: Path, psm: str = "6") -> str:
    require_command("tesseract")
    return run_command(["tesseract", str(path), "stdout", "-l", "por+eng", "--psm", psm])


def ocr_lines_from_tsv(image_path: Path) -> list[str]:
    require_command("tesseract")
    raw = run_command(
        ["tesseract", str(image_path), "stdout", "-l", "por+eng", "--psm", "6", "tsv"]
    )
    rows = csv.DictReader(io.StringIO(raw), delimiter="\t")
    grouped: dict[tuple[str, str, str], list[str]] = {}
    for row in rows:
        if row.get("level") != "5":
            continue
        text = row.get("text", "").strip()
        if not text:
            continue
        key = (row["block_num"], row["par_num"], row["line_num"])
        grouped.setdefault(key, []).append(text)
    return [" ".join(parts) for parts in grouped.values()]


def ocr_card_info(image_path: Path) -> CardInfo:
    width, height = image_size(image_path)
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        name_crop = tmp / "name.png"
        desc_crop = tmp / "description.png"

        run_command(
            [
                "magick",
                str(image_path),
                "-crop",
                f"{round(width * 0.83)}x{round(height * 0.12)}+{round(width * 0.08)}+{round(height * 0.427)}",
                "-resize",
                "300%",
                str(name_crop),
            ]
        )
        run_command(
            [
                "magick",
                str(image_path),
                "-crop",
                f"{round(width * 0.89)}x{round(height * 0.29)}+{round(width * 0.055)}+{round(height * 0.562)}",
                "-resize",
                "200%",
                str(desc_crop),
            ]
        )

        name_lines = [line.strip(" :|;") for line in ocr_file(name_crop).splitlines()]
        name_lines = [line for line in name_lines if is_probable_name_line(line)]
        title = " ".join(name_lines).strip() or image_path.stem

        desc_lines = []
        instagram = ""
        for line in ocr_file(desc_crop).splitlines():
            line = line.strip()
            if not line:
                continue
            match = re.search(r"[@Gg6Q][A-Za-z0-9_.][A-Za-z0-9_. ,]+", line)
            if match:
                instagram = clean_instagram(match.group(0))
                continue
            if "EXPER" in line.upper():
                continue
            desc_lines.append(line)

        if not instagram:
            for line in ocr_lines_from_tsv(image_path):
                match = re.search(r"[@Gg6Q][A-Za-z0-9_.][A-Za-z0-9_. ,]+", line)
                if match:
                    instagram = clean_instagram(match.group(0))
                    break

    return CardInfo(title=title, description="\n".join(desc_lines), instagram=instagram)


def is_probable_name_line(line: str) -> bool:
    if not line or "EXPER" in line.upper():
        return False
    cleaned = re.sub(r"[^A-Za-z0-9À-ÿ'!. ]", "", line).strip()
    if len(cleaned) < 3:
        return False
    if cleaned.lower() in {"logo", "cad"}:
        return False
    return True


def yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def yaml_block(value: str, indent: str = "  ") -> str:
    lines = value.strip().splitlines() or [""]
    return "\n".join(f"{indent}{line}" for line in lines)


def markdown_for(info: CardInfo, slug: str, category: str, source_name: str) -> str:
    instagram = clean_instagram(info.instagram)
    instagram_url = f"https://www.instagram.com/{instagram}/" if instagram else ""
    image_url = f"{PUBLIC_ASSETS_URL}/{category}/{slug}/experiencia.jpg"
    logo_url = f"{PUBLIC_ASSETS_URL}/{category}/{slug}/logo.png"
    source_path = f"data/instagram/{category}/{source_name}"

    return f"""---
title: {yaml_quote(info.title)}
slug: {yaml_quote(slug)}
category: {yaml_quote(category)}
instagram: {yaml_quote(instagram)}
instagramUrl: {yaml_quote(instagram_url)}
description: |-
{yaml_block(info.description)}
images:
  experience: {yaml_quote(image_url)}
  logo: {yaml_quote(logo_url)}
source:
  path: {yaml_quote(source_path)}
  filename: {yaml_quote(source_name)}
---

# {info.title}

{info.description}

Instagram: [@{instagram}]({instagram_url})
"""


def process_image(category: str, image_path: Path, dry_run: bool, use_curated: bool) -> Path:
    info = KNOWN_CARDS.get(image_path.name) if use_curated else None
    if info is None:
        info = ocr_card_info(image_path)

    slug = slugify(info.title)
    content_path = CONTENT_DIR / category / f"{slug}.md"
    asset_dir = PUBLIC_ASSETS_DIR / category / slug

    print(
        f"  {category}/{image_path.name} -> "
        f"src/content/experiencias/{category}/{slug}.md + "
        f"public/experiencias/{category}/{slug}/"
    )
    if dry_run:
        return content_path

    content_path.parent.mkdir(parents=True, exist_ok=True)
    asset_dir.mkdir(parents=True, exist_ok=True)
    crop_experience_photo(image_path, asset_dir / "experiencia.jpg")
    crop_logo(image_path, asset_dir / "logo.png")
    content_path.write_text(
        markdown_for(info, slug, category, image_path.name),
        encoding="utf-8",
    )
    return content_path


def iter_images(category: str) -> list[Path]:
    source_dir = INSTAGRAM_DIR / category
    if not source_dir.exists():
        return []
    return sorted(source_dir.glob("*.webp"))


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("category", nargs="?", choices=CATEGORIES)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--no-curated",
        action="store_true",
        help="ignore the curated table and use OCR for every image",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    require_command("magick")
    if args.no_curated:
        require_command("tesseract")

    categories = [args.category] if args.category else list(CATEGORIES)
    processed = 0

    for category in categories:
        images = iter_images(category)
        print(f"\n{category}: {len(images)} image(s)")
        for image_path in images:
            process_image(
                category=category,
                image_path=image_path,
                dry_run=args.dry_run,
                use_curated=not args.no_curated,
            )
            processed += 1

    print(f"\nDone. Processed {processed} image(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
