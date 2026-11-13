import json
from unittest.mock import Mock

import pytest

from scraper import HttpClient, Scraper


@pytest.fixture
def book_html():
    return b"""
        <div class="product_main">
            <h1> Sample Book </h1>
            <p class="star-rating Three"></p>
        </div>
        <div id="product_description"><h2>Product Description</h2></div>
        <p> A sample description. </p>
        <table><tr><th>Product Type</th><td>Books</td></tr></table>
    """


@pytest.fixture
def expected_book():
    return {
        "Product Type": "Books",
        "title": "Sample Book",
        "rating": 3,
        "description": "A sample description.",
    }


@pytest.fixture
def http_client_mock(book_html):
    client = HttpClient()
    response = Mock()

    response.content = book_html

    client.get = Mock(return_value=response)
    return client


@pytest.fixture
def scraper(http_client_mock: HttpClient):
    return Scraper(http_client_mock)


def test_get_book_data(http_client_mock, expected_book):
    scraper = Scraper(http_client=http_client_mock)
    url = "https://example.com/book"

    result = scraper.get_book_data(url)

    assert result == expected_book
    http_client_mock.get.assert_called_once_with(url)


def test_get_book_data_extracts_multiple_rows_and_strips_whitespace(
    scraper, book_html, expected_book
):
    url = "https://example.com/book"
    scraper.http_client.get.return_value.content = book_html.replace(
        b"<th>Product Type</th><td>Books</td>",
        b"<th> Product Type </th><td> Books </td>",
    ).replace(
        b"</table>",
        b"<tr><th> Number of reviews </th><td>\n  0  \n</td></tr></table>",
    )
    expected = {**expected_book, "Number of reviews": "0"}

    result = scraper.get_book_data(url)

    assert result == expected
    scraper.http_client.get.assert_called_once_with(url)


@pytest.mark.parametrize(
    ("rating_class", "expected_rating"),
    [("One", 1), ("Two", 2), ("Three", 3), ("Four", 4), ("Five", 5)],
)
def test_get_book_data_extracts_rating(
    scraper, book_html, rating_class, expected_rating
):
    scraper.http_client.get.return_value.content = book_html.replace(
        b"star-rating Three", f"{rating_class} star-rating".encode()
    )

    result = scraper.get_book_data("https://example.com/book")

    assert result["rating"] == expected_rating


def test_get_book_data_without_description(scraper, book_html):
    scraper.http_client.get.return_value.content = book_html.replace(
        b'<div id="product_description"><h2>Product Description</h2></div>', b""
    )

    result = scraper.get_book_data("https://example.com/book")

    assert result["description"] == ""


def test_scrape_books_uses_index_fallback_and_saves_data(
    scraper, tmp_path, book_html, expected_book
):
    base_url = "http://books.toscrape.com"
    category_url = f"{base_url}/catalogue/category/books_1/"
    filepath = tmp_path / "books_data.txt"
    responses = {
        f"{base_url}/index.html": Mock(status_code=200, content=b"<html></html>"),
        f"{category_url}page-1.html": Mock(status_code=404, content=b"Not found"),
        f"{category_url}index.html": Mock(
            status_code=200,
            content=b"""
                <section>
                    <article class="product_pod">
                        <a href="../../../sample-book_1/index.html">Cover</a>
                        <h3>
                            <a href="../../../sample-book_1/index.html">Book</a>
                        </h3>
                    </article>
                </section>
            """,
        ),
        f"{base_url}/catalogue/sample-book_1/index.html": Mock(
            status_code=200,
            content=book_html,
        ),
    }
    scraper.http_client.get.side_effect = responses.__getitem__
    expected = {category_url: [expected_book]}

    result = scraper.scrape_books(
        is_save=True,
        left=1,
        right=2,
        catalogue="books_1",
        filepath=filepath,
    )

    scraper.http_client.get.assert_any_call(f"{category_url}index.html")
    assert result == expected
    assert json.loads(filepath.read_text()) == expected


@pytest.mark.parametrize(
    "navigation",
    [
        "",
        '<li class="previous"><a href="page-1.html">previous</a></li>',
        '<li class="next"><a href="page-3.html">next</a></li>',
        (
            '<li class="previous"><a href="page-1.html">previous</a></li>'
            '<li class="next"><a href="page-3.html">next</a></li>'
        ),
    ],
    ids=["no-navigation", "previous", "next", "previous-and-next"],
)
def test_scrape_books_ignores_navigation_links(
    scraper, book_html, expected_book, navigation
):
    base_url = "http://books.toscrape.com"
    category_url = f"{base_url}/catalogue/category/books_1/"
    book_url = f"{base_url}/catalogue/sample-book_1/index.html"
    responses = {
        f"{base_url}/index.html": Mock(status_code=200, content=b"<html></html>"),
        f"{category_url}page-2.html": Mock(
            status_code=200,
            content=(
                '<section><article class="product_pod"><h3>'
                '<a href="../../../sample-book_1/index.html">Book</a>'
                f'</h3></article><ul class="pager">{navigation}</ul></section>'
            ).encode(),
        ),
        book_url: Mock(status_code=200, content=book_html),
    }
    scraper.http_client.get.side_effect = responses.__getitem__

    result = scraper.scrape_books(is_save=False, left=2, right=3, catalogue="books_1")

    assert result == {category_url: [expected_book]}
    assert [call.args[0] for call in scraper.http_client.get.call_args_list] == [
        f"{base_url}/index.html",
        f"{category_url}page-2.html",
        book_url,
    ]
