import json
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


class HttpClient:
    """HTTP-клиент-обертка над requests для упрощения тестирования."""
    def get(self, url: str):
        """GET-запрос"""
        return requests.get(url)


class Scraper:
    """Класс скраппера инкапсулирующий логику."""

    def __init__(self, http_client: HttpClient):
        self.http_client = http_client

    def get_book_data(self, book_url: str) -> dict:
        """Вычленяет информацию о продукте из тега таблицы в html по url.

        Attrs:
        book_url: Ссылка на продукт в виде строки
        Returns:
        Словарь данных из таблицы продукта.

        Пример:
        {
            "UPC": "a897fe39b1053632",
            "Product Type": "Books",
            "Price (excl. tax)": "£51.77",
            "Price (incl. tax)": "£51.77",
            "Tax": "£0.00",
            "Availability": "In stock (22 available)",
            "Number of reviews": "0",
        }
        """
        resp = self.http_client.get(book_url)
        soup = BeautifulSoup(resp.content, features="html.parser")

        # На странице с описанием книги только один тег таблица
        table = soup.find("table")

        data = {}
        for row in table.find_all("tr"):
            key = row.find("th").get_text(strip=True)
            value = row.find("td").get_text(strip=True)
            data[key] = value

        return data

    @staticmethod
    def save_file(data: str, filepath: Path):
        filepath.write_text(data)


    def scrape_books(
        self,
        is_save: bool,
        left: int,
        right: int,
        catalogue: str | None = None,
        filepath: Path | None = None,
    ):
        """Выгружает информацию о книгах и сохраняет в books_data.txt если задан флаг is_save.

        Attrs:
        is_save: Флаг сохранения выгрузки в books_data.txt
        left: Левая граница книг каталога
        right: Правая граница книг каталога
        Returns:
        Словарь данных из таблицы продукта.
        """
        base_url = "http://books.toscrape.com"
        resp = self.http_client.get(f"{base_url}/index.html")
        index_page = BeautifulSoup(resp.content, features="html.parser")

        if not catalogue:
            catalogues_links = [
                link.get("href")
                for link in index_page.find("div", class_="side_categories").find_all("a")
            ]
            catalogues = [urljoin(base_url, link) for link in catalogues_links]
        else:
            catalogues = [urljoin(base_url, f"/catalogue/category/{catalogue}/")]

        catalogue_books_map = {}
        for cat in catalogues:
            books_data = []
            for n in range(left, right):
                page_url = urljoin(cat, f"page-{n}.html")

                resp = self.http_client.get(page_url)
                if resp.status_code == 404 and n != 1:
                    break

                if resp.status_code == 404:
                    page_url = urljoin(cat, "index.html")
                    resp = self.http_client.get(page_url)

                category_page = BeautifulSoup(resp.content)

                books_links = category_page.find("section").find_all("a")
                hrefs = [link.get("href").split("../")[-1] for link in books_links][:-1]

                books = {urljoin(base_url, f"/catalogue/{ref}") for ref in hrefs}

                for book in books:
                    books_data.append(self.get_book_data(book))

            catalogue_books_map[cat] = books_data

        if is_save:
            filepath = filepath or Path("books_data.txt")
            self.save_file(json.dumps(catalogue_books_map, ensure_ascii=False), filepath)
        return catalogue_books_map
