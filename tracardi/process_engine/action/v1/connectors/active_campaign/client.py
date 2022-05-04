import aiohttp


class ActiveCampaignClientException(Exception):
    pass


class ActiveCampaignClient:

    def __init__(self, api_key: str, api_url: str):
        self.api_key = api_key
        self.api_url = api_url

    async def send_contact(self, data: dict):
        data = {key: data[key] for key in data if data[key] is not None}
        data["fieldValues"] = [{"field": key, "value": data[key]} for key in data if key.isnumeric()]

        async with aiohttp.ClientSession(headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "api-token": self.api_key
        }) as session:

            if "email" in data:

                async with session.post(
                    url=f"{self.api_url}/api/3/contacts",
                    json={"contact": data}
                ) as response:

                    if response.status != 201:
                        if (await response.json())['errors'][0]["code"] == "duplicate":
                            contact = (await self.get_contact_by_email(data["email"]))
                            async with session.put(
                                url=f"{self.api_url}/api/3/contacts/{contact['id']}",
                                json={"contact": {key: data[key] for key in data if key != "email"}}
                            ) as put_response:

                                if put_response.status != 200:
                                    raise ActiveCampaignClientException(await put_response.text())

                                return await put_response.json()

                        else:
                            raise ActiveCampaignClientException(await response.text())

                    return await response.json()

            elif "id" in data:
                async with session.put(
                        url=f"{self.api_url}/api/3/contacts/{data['id']}",
                        json={"contact": {key: data[key] for key in data}}
                ) as put_response:

                    if put_response.status != 200:
                        raise ActiveCampaignClientException(await put_response.text())

                    return await put_response.json()

            else:
                raise ActiveCampaignClientException("One of: id, email parameters has to be provided.")

    async def get_custom_fields(self):
        async with aiohttp.ClientSession(headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "api-token": self.api_key
        }) as session:
            async with session.get(f"{self.api_url}/api/3/fields") as response:

                if response.status != 200:
                    raise ActiveCampaignClientException(await response.text())

                return [{"label": field["title"], "value": field["id"]} for field in (await response.json())["fields"]]

    async def get_contact_by_email(self, email: str):
        async with aiohttp.ClientSession(headers={
            "Accept": "application/json",
            "Content-Type": "application/json",
            "api-token": self.api_key
        }) as session:
            async with session.get(f"{self.api_url}/api/3/contacts?email={email}") as response:

                if response.status != 200:
                    raise ActiveCampaignClientException(await response.text())

                response = (await response.json())["contacts"]

                try:
                    return response[0]
                except IndexError:
                    raise ActiveCampaignClientException(f"No contacts found for email {email}")

