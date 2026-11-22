-- Dialect: PostgreSQL

-- Шаг 3

-- 1. Выведите id продукта и среднюю цену продажи (item_list_price_at_sale)
-- для 5 продуктов с самой высокой средней ценой продажи.

SELECT
	product_id,
	AVG(item_list_price_at_sale) AS avg_price
FROM
	order_items
GROUP BY
	product_id
ORDER BY
	avg_price DESC,
	product_id
LIMIT 5;

-- 2. Рассчитайте общую стоимость заказа (item_list_price_at_sale * quantity) для каждого бренда продукта.

SELECT
	p.brand,
	SUM(oi.item_list_price_at_sale * quantity) AS total_price
FROM
	order_items oi
JOIN products p ON
	oi.product_id = p.product_id
GROUP BY
	p.brand;


-- 3. Подсчитайте количество заказов за каждый месяц для каждого года. То есть необходимо вывести год, месяц и количество заказов.

SELECT
	date_part('year', order_date::DATE) AS "year"
	,
	DATE_PART('month', order_date::DATE) AS "month"
	,
	count(DISTINCT order_id) AS orders
FROM
	orders
GROUP BY
	"month",
	"year"
ORDER BY
	"year",
	"month";


-- 4. Для каждой продуктовой линейки (product_line) найдите продукт с самой высокой стандартной стоимостью (standard_cost).
-- Выведите id продукта, линейку продукта и стандартную стоимость.


SELECT
	p1.product_id,
	p1.product_line,
	p1.standard_cost
FROM
	products p1
JOIN (
	SELECT
		max(standard_cost) AS max_standard_cost,
		product_line
	FROM
		products
	GROUP BY
		product_line) p2 ON
	p2.max_standard_cost = p1.standard_cost
	AND p1.product_line = p2.product_line
;



-- 5. Подсчитайте количество заказов и общую стоимость заказов для каждого статуса заказа (order_status).
-- Общую стоимость заказа необходимо рассчитать как цену продукта на момент продажи, умноженную на количество единиц продукта в заказе.


SELECT
	order_status,
	count(o.order_id) AS orders_amount,
	sum(os.order_sum) AS total_sum
FROM
	orders o
JOIN (
	SELECT
		order_id,
		SUM(item_list_price_at_sale * quantity) AS order_sum
	FROM
		order_items
	GROUP BY
		order_id) os ON
	o.order_id = os.order_id
GROUP BY o.order_status;


-- 6. Найдите клиентов, у которых нет ни одного заказа. Выведите id клиента, фамилию и имя.

SELECT
	c.customer_id,
	c.last_name,
	c.first_name
FROM
	customers c
WHERE
	c.customer_id NOT IN (
	SELECT
		customer_id
	FROM
		orders);

-- 7. Для каждого штата найдите клиента с самой высокой и самой низкой оценкой стоимости имущества (property_valuation).
-- Выведите штат, оценку стоимости имущества, фамилию и имя клиента.


SELECT
	c1.state,
	c1.property_valuation,
	c1.last_name,
	c1.first_name
FROM
	customers c1
JOIN (
	SELECT
		state,
		max(c2.property_valuation) AS max_property_valuation,
		min(c2.property_valuation) AS min_property_valuation
	FROM
		customers c2
	GROUP BY
		state) c_aggr
ON
	c1.state = c_aggr.state
	AND (c1.property_valuation = c_aggr.max_property_valuation
		OR c1.property_valuation = c_aggr.min_property_valuation)
ORDER BY c1.state;


-- 8. Найдите клиентов, которые покупали продукты только из одной продуктовой линейки (product_line).
-- Выведите id клиента, линейку продукта и количество заказов.

SELECT 
	o.customer_id
	,max(p.product_line) AS product_line
	,count(DISTINCT oi.order_id) AS orders_amount
FROM order_items oi
JOIN products p ON
	oi.product_id = p.product_id
JOIN orders o ON
	oi.order_id = o.order_id
GROUP BY o.customer_id
HAVING count(DISTINCT p.product_line) = 1
	; 

--- Или
WITH cnt AS (
SELECT
	customer_id,
	COUNT(DISTINCT product_line) AS line_cnt
FROM order_items oi
JOIN products p ON
	oi.product_id = p.product_id
JOIN orders o ON
	oi.order_id = o.order_id
GROUP BY customer_id
)
SELECT 
	o.customer_id,
	p.product_line, 
	COUNT (DISTINCT o.order_id) AS cnt
FROM order_items oi
JOIN products p ON
	oi.product_id = p.product_id
JOIN orders o ON
	oi.order_id = o.order_id
JOIN cnt ON 
	cnt.customer_id = o.customer_id 
WHERE line_cnt = 1
GROUP BY 1, 2;


-- 9. Для каждой категории продуктов рассчитайте процент отмененных заказов (order_status = 'Cancelled').

-- Здесь LLM помог мне отловить баг с DISTINCT и с подсчетом заказов без отмененных.

WITH order_to_product_line AS (
SELECT
	oi.order_id,
	p.product_line
FROM
	order_items oi
JOIN products p ON
	p.product_id = oi.product_id
)

,
cancelled_orders_to_product_line AS (
SELECT
	count(DISTINCT o1.order_id) AS cancelled_count,
	otpl.product_line
FROM
	orders o1
JOIN order_to_product_line otpl ON
	otpl.order_id = o1.order_id
WHERE
	o1.order_status = 'Cancelled'
GROUP BY
	otpl.product_line
)
, 

all_orders_to_product_line AS (
SELECT
	count(DISTINCT o1.order_id) AS all_count,
	otpl.product_line
FROM
	orders o1
JOIN order_to_product_line otpl ON
	otpl.order_id = o1.order_id
GROUP BY
	otpl.product_line
)

SELECT
	aotpl.product_line
	,to_char((coalesce(cotpl.cancelled_count, 0)::float / aotpl.all_count::float)*100, '990D99%') AS cancelled_order_percentage
FROM
	cancelled_orders_to_product_line cotpl
RIGHT JOIN all_orders_to_product_line aotpl ON
	cotpl.product_line = aotpl.product_line
;

-- 10. Разделите клиентов на сегменты на основе количества заказов и подсчитайте количество клиентов в каждом сегменте:
-- сегмент High, если количество заказов больше 10;
-- сегмент Medium, если количество заказов от 5 до 10;
-- иначе сегмент Low.

WITH cte AS (
SELECT
	customer_id,
	count(order_id) AS orders_amount
FROM
	orders
GROUP BY
	customer_id
)

SELECT
	count(customer_id),
	CASE
		WHEN orders_amount > 10 THEN 'High'
		WHEN orders_amount > 5
		AND orders_amount <= 10 THEN 'Medium'
		WHEN orders_amount <= 5 THEN 'Low'
	END AS segments
FROM
	cte
GROUP BY
	segments
;

--
----- Или
--
--
--SELECT
--	count(o.customer_id),
--	CASE
--		WHEN count(o.order_id) > 10 THEN 'High'
--		WHEN count(o.order_id) > 5
--		AND count(o.order_id) <= 10 THEN 'Medium'
--		WHEN count(o.order_id) <= 5 THEN 'Low'
--	END AS segments
--	FROM
--		orders o
--	GROUP BY
--		o.customer_id
--group BY count(o.order_id) DESC ;


-- 11. Для всех клиентов выведите имена, фамилии, профессии, а также длительность максимального интервала (в днях)
-- между двумя последовательными заказами. Необходимо исключить клиентов, у которых только один заказ или меньше.

-- LLM подсказал, что customers_to_exclude избыточен, потому что в customer_order_diff итак не находят подходящей пары в join

-- Находим разницу в днях между покупками для каждого клиента
WITH customer_order_diff AS (
SELECT
	o1.customer_id,
	--o1.order_date,
	min(o2.order_date::date) - o1.order_date::date AS days_diff
FROM
	orders o1
JOIN orders o2 ON
	o1.customer_id = o2.customer_id
	AND o1.order_date < o2.order_date
GROUP BY
	o1.customer_id,
	o1.order_date
ORDER BY
	o1.customer_id,
	o1.order_date
)

SELECT
	c.first_name,
	c.last_name,
	c.job_title,
	max(cod.days_diff) AS max_order_days_interval
FROM
	customers c
JOIN customer_order_diff cod ON
	c.customer_id = cod.customer_id
GROUP BY c.first_name, c.last_name, c.job_title, c.customer_id;
