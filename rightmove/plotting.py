from typing import List

import pandas as pd
import plotly.graph_objects as go


def create_mapbox(properties: List[dict]) -> str:

    df = pd.DataFrame.from_records(properties)
    df["url"] = df.apply(
        lambda x: f'<a href="{x["link"]}" style="color: #00dcb5;">{x["title"]}</a>',
        axis=1,
    )

    hovertemplate = "<b>%{customdata[0]}</b><br>%{customdata[1]}<br>%{customdata[2]}"

    fig = go.Figure(
        go.Scattermapbox(
            mode="markers",
            lon=df.longitude,
            lat=df.latitude,
            customdata=df[["url", "address", "price"]],
            marker={"size": 10, "symbol": "castle", "allowoverlap": True},
            textposition="bottom right",
            name="",
            hovertemplate=hovertemplate,
            hoverlabel={"namelength": -1, "bgcolor": "rgba(255, 255, 255, 0.9)"},
        )
    )

    fig.update_layout(
        mapbox={
            "accesstoken": "pk.eyJ1IjoiYWRhbWpvbmVzIiwiYSI6ImNrb3c0M3V6MDAya2QydnJ3cWtwN3VsZWQifQ.JBoPpcnRJE7AX_dq0YAOyA",
            "style": "streets",
            "center": {"lon": -0.1, "lat": 51.5},
            "zoom": 10,
        },
        margin=dict(l=5, r=5, t=5, b=5),
        showlegend=False,
    )

    return fig.to_html()
