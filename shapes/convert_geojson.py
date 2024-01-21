import json


def convert_file(file: str) -> None:
    with open(file) as f:
        data = json.load(f)

    if data.get("type") != "FeatureCollection":
        raise ValueError("File is not a FeatureCollection.")

    shell = []
    for feature in data["features"]:
        for coordinates in feature["geometry"]["coordinates"]:
            for coordinate in coordinates:
                shell.append({"lat": coordinate[1], "lon": coordinate[0]})

    output = {
        "shapes": [{"shell": shell}],
    }

    with open(file, "w") as f:
        json.dump(output, f, indent=4)


if __name__ == "__main__":
    convert_file("exclude_north_east.json")
