"""Pin local OFL-licensed Inter instances for robust PDF font embedding."""
from pathlib import Path
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

root = Path(__file__).resolve().parent
source = root.parent / "design/fonts/inter-latin-c940764593d0.woff2"
destination = root / "font-assets"
destination.mkdir(exist_ok=True)
for weight in [400, 550, 650, 700]:
    variable = TTFont(source)
    axes = {axis.axisTag: axis.defaultValue for axis in variable["fvar"].axes}
    axes["wght"] = weight
    instance = instantiateVariableFont(variable, axes, inplace=False)
    instance.flavor = None
    for record in instance["name"].names:
        values = {1: "SPACE Report Inter", 2: f"Weight {weight}", 4: f"SPACE Report Inter {weight}", 6: f"SPACEReportInter-{weight}"}
        if record.nameID in values:
            record.string = values[record.nameID].encode(record.getEncoding())
    instance.save(destination / f"inter-print-{weight}.ttf")
print("Four static PDF font instances generated from local OFL-licensed Inter; no font downloaded.")
