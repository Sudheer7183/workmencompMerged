--
-- PostgreSQL database dump
--

\restrict mzcYoA6K51y8NcEW7dVPyPpbJVOxzB0ny61ytxfVfb312fJWiYaLbNZxdsIyN4U

-- Dumped from database version 16.14 (Debian 16.14-1.pgdg13+1)
-- Dumped by pg_dump version 16.14 (Debian 16.14-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Data for Name: users; Type: TABLE DATA; Schema: tenant_demo; Owner: auditplatform
--

COPY tenant_demo.users (user_id, keycloak_id, role, email, first_name, last_name, is_active, onboarding_completed, created_at, deleted_at) FROM stdin;
4	759b6e4a-6741-491b-96d8-a0b902c61b62	TENANT_ADMIN	admin@demo.platform.local	Demo	Admin	t	t	2026-06-02 14:14:12.626213+00	\N
5	c5fa0b1e-aef1-49c1-a53b-d08ec9b8c5c8	AUDITOR	auditor@demo.platform.local	Demo	Auditor	t	t	2026-06-02 14:14:12.626213+00	\N
6	9196231c-2183-4850-9443-f30f2848d041	REVIEWER	reviewer@demo.platform.local	Demo	Reviewer	t	t	2026-06-02 14:14:12.626213+00	\N
\.


--
-- Name: users_user_id_seq; Type: SEQUENCE SET; Schema: tenant_demo; Owner: auditplatform
--

SELECT pg_catalog.setval('tenant_demo.users_user_id_seq', 6, true);


--
-- PostgreSQL database dump complete
--

\unrestrict mzcYoA6K51y8NcEW7dVPyPpbJVOxzB0ny61ytxfVfb312fJWiYaLbNZxdsIyN4U

