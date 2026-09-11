import marimo

__generated_with = "0.24.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import altair as alt
    import marimo as mo
    import numpy as np
    import polars as pl

    return alt, mo, np, pl


@app.cell
def _(mo):
    mo.md(r"""
    # Interactive Quantitative Research Notebook
    This notebook simulates a synthetic random-walk price series:
    $$\Delta P_t \sim \mathcal{N}(0, \sigma)$$

    Adjust parameters via controls to observe updates in real time.
    """)
    return


@app.cell
def _(mo):
    # Reactive Control Widgets
    n_obs_slider = mo.ui.slider(
        start=100, stop=5000, step=50, value=1000, label="Observations (N)"
    )
    vol_slider = mo.ui.slider(
        start=0.1, stop=5.0, step=0.1, value=1.0, label="Volatility (σ)"
    )
    seed_number = mo.ui.number(
        start=1, stop=9999, value=42, label="Random Seed"
    )
    sma_slider = mo.ui.slider(
        start=5, stop=200, step=5, value=20, label="SMA Window Size"
    )

    mo.hstack(
        [
            mo.vstack([n_obs_slider, vol_slider]),
            mo.vstack([seed_number, sma_slider]),
        ]
    )
    return n_obs_slider, seed_number, sma_slider, vol_slider


@app.cell
def _(n_obs_slider, np, pl, seed_number, vol_slider):
    # Data Generation Cell (Only recalculates when data inputs change)
    N = n_obs_slider.value
    sigma = vol_slider.value
    seed = int(seed_number.value)

    np.random.seed(seed)
    price_changes = np.random.normal(0, sigma, N)
    prices = 100.0 + np.cumsum(price_changes)

    df_raw = pl.DataFrame(
        {
            "step": np.arange(1, N + 1),
            "price_change": price_changes,
            "price": prices,
        }
    )
    return N, df_raw, seed, sigma


@app.cell
def _(df_raw, pl, sma_slider):
    # Analytics Calculation Cell (Recalculates on SMA window changes)
    window_size = sma_slider.value

    df_processed = df_raw.with_columns(
        pl.col("price").rolling_mean(window_size=window_size).alias("sma")
    )

    stats = df_processed.select(
        [
            pl.col("price").min().alias("min_price"),
            pl.col("price").max().alias("max_price"),
            pl.col("price").mean().alias("avg_price"),
            pl.col("price_change").std().alias("std_change"),
        ]
    ).to_dicts()[0]
    return df_processed, stats, window_size


@app.cell
def _(alt, df_processed):
    # Direct Chart Rendering (Bypasses virtual file system memory storing before rendering 
    #                         avoiding disk I/O and memory leak issues)
    df_melted = df_processed.select(["step", "price", "sma"]).unpivot(
        index="step",
        on=["price", "sma"],
        variable_name="Series",
        value_name="Value",
    )

    chart = (
        alt.Chart(df_melted)
        .mark_line()
        .encode(
            x=alt.X("step:Q", title="Step"),
            y=alt.Y("Value:Q", title="Price ($)", scale=alt.Scale(zero=False)),
            color=alt.Color(
                "Series:N",
                scale=alt.Scale(
                    domain=["price", "sma"], range=["#1f77b4", "#ff7f0e"]
                ),
            ),
            tooltip=["step", "Series", "Value"],
        )
        .properties(
            title="Simulated Price Series vs Moving Average",
            width=700,
            height=350,
        )
        .interactive()
    )

    chart
    return


@app.cell
def _(N, mo, seed, sigma, stats, window_size):
    # Summary Display Panel
    summary_md = f"""
    ### Experiment Summary
    * **Parameters**: $N = {N}$, $\sigma = {sigma}$, Seed = `{seed}`, Window = `{window_size}`
    * **Min Price**: `${stats['min_price']:.2f}`
    * **Max Price**: `${stats['max_price']:.2f}`
    * **Avg Price**: `${stats['avg_price']:.2f}`
    * **Std Dev (Price Changes)**: `{stats['std_change']:.4f}`
    """
    mo.md(summary_md)
    return


if __name__ == "__main__":
    app.run()
