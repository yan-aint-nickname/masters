import json
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


class HttpClient:
    """HTTP-клиент на базе requests с возможностью подмены в тестах."""

    def get(self, url: str):
        """Выполняет GET-запрос по указанному URL.

        Args:
            url: URL запрашиваемой страницы.

        Returns:
            Ответ requests.Response без проверки HTTP-статуса.

        Raises:
            requests.RequestException: Не удалось выполнить запрос.
        """
        return requests.get(url)


class Scraper:
    """Сборщик характеристик книг с сайта Books to Scrape.

    Attributes:
        http_client: Клиент HttpClient для загрузки страниц.
    """

    def __init__(self, http_client: HttpClient):
        """Инициализирует сборщик с переданным HTTP-клиентом.

        Args:
            http_client: Клиент для загрузки страниц.
        """
        self.http_client = http_client

    def get_book_data(self, book_url: str) -> dict:
        """Возвращает данные книги и характеристики из Product Information.

        Args:
            book_url: URL страницы книги с таблицей характеристик.

        Returns:
            Словарь с title (название), rating (целое число от 1 до 5),
            description (описание или пустая строка, если его нет) и строковыми
            характеристиками из таблицы. Пробелы по краям текста удалены.

        Raises:
            requests.RequestException: Не удалось загрузить страницу книги.
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

        data["title"] = soup.find("h1").get_text(strip=True)

        ratings = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
        rating_classes = soup.find("p", class_="star-rating")["class"]
        data["rating"] = next(
            ratings[name] for name in rating_classes if name in ratings
        )

        description = soup.select_one("#product_description + p")
        data["description"] = (
            description.get_text(" ", strip=True) if description else ""
        )

        return data

    @staticmethod
    def save_file(data: str, filepath: Path):
        """Записывает текст в файл, заменяя его содержимое, если он существует.

        Args:
            data: Текст для записи.
            filepath: Путь к файлу в существующем каталоге.

        Raises:
            OSError: Не удалось записать файл.
        """
        filepath.write_text(data)

    def scrape_books(
        self,
        is_save: bool,
        left: int,
        right: int,
        catalogue: str | None = None,
        filepath: Path | None = None,
    ):
        """Собирает характеристики книг с необязательным сохранением в JSON.

        Args:
            is_save: Сохранить результат в файл в формате JSON.
            left: Номер первой страницы для сбора, начиная с 1.
            right: Верхняя граница номеров страниц, не включая её.
            catalogue: Путь относительно /catalogue/category/, например
                "books_1". Если не задан, используются ссылки бокового каталога.
            filepath: Путь к файлу результата. По умолчанию — books_data.txt
                в текущем рабочем каталоге. Учитывается только при is_save=True;
                существующий файл перезаписывается.

        Returns:
            Словарь, где ключи — URL каталогов, а значения — списки словарей
            характеристик книг, возвращённых get_book_data.

        Raises:
            requests.RequestException: Не удалось загрузить страницу.
            OSError: Не удалось сохранить результат при is_save=True.
        """
        base_url = "http://books.toscrape.com"
        resp = self.http_client.get(f"{base_url}/index.html")
        index_page = BeautifulSoup(resp.content, features="html.parser")

        if not catalogue:
            catalogues_links = [
                link.get("href")
                for link in index_page.find("div", class_="side_categories").find_all(
                    "a"
                )
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

                category_page = BeautifulSoup(resp.content, features="html.parser")

                books_links = category_page.find("section").find_all("a")
                navigation_links = category_page.select("li.previous a, li.next a")

                hrefs = [
                    link.get("href").split("../")[-1]
                    for link in books_links
                    if link not in navigation_links
                ]

                books = {urljoin(base_url, f"/catalogue/{ref}") for ref in hrefs}

                for book in books:
                    books_data.append(self.get_book_data(book))

            catalogue_books_map[cat] = books_data

        if is_save:
            filepath = filepath or Path("books_data.txt")
            self.save_file(
                json.dumps(catalogue_books_map, ensure_ascii=False), filepath
            )
        return catalogue_books_map
