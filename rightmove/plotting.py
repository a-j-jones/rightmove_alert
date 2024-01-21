from typing import List

import pandas as pd
import plotly.graph_objects as go


def create_mapbox(properties: List[dict]) -> str:

    df = pd.DataFrame.from_records(properties)
    df["symbol"] = "castle"

    fig = go.Figure(
        go.Scattermapbox(
            mode="markers",
            lon=df.longitude,
            lat=df.latitude,
            marker={"size": 10},
            textposition="bottom right",
        )
    )

    fig.update_layout(
        mapbox={
            "accesstoken": "pk.eyJ1IjoiYWRhbWpvbmVzIiwiYSI6ImNrb3c0M3V6MDAya2QydnJ3cWtwN3VsZWQifQ.JBoPpcnRJE7AX_dq0YAOyA",
            "style": "basic",
            "center": {"lon": 0.01, "lat": 51.5},
            "zoom": 10,
        },
        margin=dict(l=5, r=5, t=5, b=5),
        showlegend=False,
    )

    return fig.to_html()
