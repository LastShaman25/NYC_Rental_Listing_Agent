"""Map-first internal review workbench (07; 08 §16).

Entry point wiring the multipage navigation. Pages render read models from
ui/queries.py and call canonical services for writes; no business rules live in
page code (07 §23.1). Long work is never run inline (07 §5.4).

Run: uv run streamlit run src/rental_agent/ui/app.py --server.address 127.0.0.1
"""

import streamlit as st

from rental_agent.config.settings import load_settings
from rental_agent.db.engine import build_engine, build_session_factory


@st.cache_resource
def session_factory():
    settings = load_settings()
    return build_session_factory(build_engine(settings)), settings


def main() -> None:
    st.set_page_config(page_title="Rental Listing Agent", layout="wide")
    factory, settings = session_factory()

    from rental_agent.ui.pages import (
        dashboard,
        inventory_page,
        listing_detail_page,
        operations_page,
        review_page,
        selected_page,
    )

    pages = st.navigation(
        [
            st.Page(dashboard.render, title="Dashboard", icon="📊", default=True),
            st.Page(inventory_page.render, title="Inventory", icon="🗺️", url_path="inventory"),
            st.Page(
                listing_detail_page.render, title="Listing Detail", icon="🏠", url_path="detail"
            ),
            st.Page(selected_page.render, title="Selected", icon="⭐", url_path="selected"),
            st.Page(review_page.render, title="Review Queue", icon="🧐", url_path="review"),
            st.Page(operations_page.render, title="Operations", icon="⚙️", url_path="operations"),
        ]
    )
    st.sidebar.caption(f"profile: {settings.profile.value} · operator: {settings.operator_id}")
    pages.run()


if __name__ == "__main__":
    main()
