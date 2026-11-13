from unittest.mock import Mock

import pytest

from scraper import HttpClient, Scraper


@pytest.fixture
def http_client_mock():
    client = HttpClient()
    response = Mock()

    response.content = b"<table><tr><th>Product Type</th><td>Books</td></tr></table>"

    client.get = Mock(return_value=response)
    return client


@pytest.fixture
def scraper(http_client_mock: HttpClient):
    return Scraper(http_client_mock)


def test_get_book_data(http_client_mock):
    scraper = Scraper(http_client=http_client_mock)
    url = "https://example.com/book"

    result = scraper.get_book_data(url)

    assert result == {"Product Type": "Books"}
    http_client_mock.get.assert_called_once_with(url)


def test_get_book_data_extracts_multiple_rows_and_strips_whitespace(scraper):
    url = "https://example.com/book"
    scraper.http_client.get.return_value.content = b"""
        <table>
            <tr><th> Product Type </th><td> Books </td></tr>
            <tr>
                <th> Number of reviews </th>
                <td>\n  0  \n</td>
            </tr>
        </table>
    """
    expected = {"Product Type": "Books", "Number of reviews": "0"}

    result = scraper.get_book_data(url)

    assert result == expected
    scraper.http_client.get.assert_called_once_with(url)
