# The message to the Tribune Desk contact

Tribune Desk sets up each integration by hand: there is no self-service sign-up. The items to
request come **only** from the table "What to ask Tribune Desk for" in the downloaded
`README.md`, the rows of the chosen levels and mode. Copy the wording of those rows into the
list; do not add items from memory and do not leave rows out.

Fill in the brackets. Leave out the webhook line in read mode and for level 4 only. Never put a
secret or token value in the message: the contact sends them to the user, not the other way.

For level 4 add one line after the list: a separate test organization (with its own token) for
the staging and development copies of the CMS. One organization has one feed position, so a
copy on the production organization muddles it (`guide/4-media-library.md`, The sync cycle).

## English

> Subject: Tribune Desk CMS integration for [organization]
>
> Hello,
>
> We are connecting our CMS ([CMS name and version]) to Tribune Desk at levels [levels]
> ([webhook / read mode]) of the CMS API, contract [version].
>
> Webhook address: [https://… , or "we will send it once it is deployed"]
>
> Please set up for our organization:
>
> - [one line per item from the README table rows]
>
> We are building and testing against a local mock in the meantime, so there is no rush on our
> side. Thank you!

## Polski

> Temat: integracja CMS z Tribune Desk dla [organizacja]
>
> Dzień dobry,
>
> łączymy nasz CMS ([nazwa i wersja]) z Tribune Desk na poziomach [poziomy] API CMS
> ([webhook / tryb odczytu]), kontrakt [wersja].
>
> Adres webhooka: [https://… , albo „podamy po wdrożeniu”]
>
> Prosimy o przygotowanie dla naszej organizacji:
>
> - [po jednej linii na każdą pozycję z wierszy tabeli README]
>
> Do czasu odpowiedzi budujemy i testujemy na lokalnej atrapie, więc z naszej strony nic nie
> pilnuje. Dziękujemy!

When the user writes in another language, write the message in that language with the same
frame.
