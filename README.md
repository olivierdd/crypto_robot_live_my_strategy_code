# crypto_robot_live_my_strategy_code
Implémentation Python de la stratégie Envelope de Crypto Robot

Le code nécessite un certain nombre de librairies, à installer séparément :
- os
- sys
- ta
- datetime
- json
- uuid
- logging

Et une librairie qui fait partie du projet
- perp_bybit

Il est également nécessaire de créer un fichier 'secret.json' à placer dans le répertoire principal du projet
Ce fichier devra contenir les clés API de Bybit. Vous pouvez y mettre à la fois les clé de votre compte testnet.bybit.com
et celles de votre compte réel. Dans le format suivant :
{
    "real_account": {
        "apiKey":"votre_clé",
        "secret":"votre_clé",
        "is_real":"True"
    },
    "testnet_account": {
        "apiKey":"votre_clé",
        "secret":"votre_clé",
        "is_real":"False"
    }
}
