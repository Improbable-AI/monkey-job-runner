db.createUser(
    {
        "user": "monkeycore",
        "pwd": "bananas",
        "roles": [
            {
                "role": "readWrite",
                "db": "monkeydb"
            }
        ]
    }
)
