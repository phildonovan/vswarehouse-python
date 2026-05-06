from __future__ import annotations

import pandas as pd


class VSeries(pd.DataFrame):
    """A pandas DataFrame with vs-warehouse series metadata.

    Behaves exactly like a DataFrame — all pandas operations work normally.
    Extra attributes:
        vs_name:   Series identifier (e.g. "nz_cpi").
        vs_source: Data source label (e.g. "Stats NZ").
    """

    _metadata = ["vs_name", "vs_source"]

    @property
    def _constructor(self):
        return VSeries

    def __repr__(self) -> str:
        name   = getattr(self, "vs_name",   "") or ""
        source = getattr(self, "vs_source", "") or ""
        if name:
            header = f"# VSeries: {name}"
            if source:
                header += f" [{source}]"
            header += f"\n# {len(self)} rows\n"
            return header + pd.DataFrame.__repr__(self)
        return pd.DataFrame.__repr__(self)

    def plot_series(self, ax=None, **kwargs):
        """Quick line chart using matplotlib.

        Returns the matplotlib Axes object so you can customise further.
        Requires matplotlib: ``pip install matplotlib``.
        """
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            raise ImportError(
                "matplotlib is required for plot_series(). "
                "Install with: pip install matplotlib"
            )

        date_col  = "date"  if "date"  in self.columns else self.columns[0]
        value_col = "value" if "value" in self.columns else self.columns[1]

        if ax is None:
            _, ax = plt.subplots(figsize=(10, 4))

        ax.plot(self[date_col], self[value_col], color="#2563eb", linewidth=1.5, **kwargs)

        name   = getattr(self, "vs_name",   "") or ""
        source = getattr(self, "vs_source", "") or ""

        if name:
            ax.set_title(name, fontweight="bold", fontsize=13)
        ax.set_xlabel("")
        ax.spines[["top", "right"]].set_visible(False)

        caption = f"Source: {source} · api.virtus-solutions.io" if source else "api.virtus-solutions.io"
        ax.figure.text(0.99, 0.01, caption, ha="right", fontsize=8, color="#9ca3af")

        plt.tight_layout()
        return ax
