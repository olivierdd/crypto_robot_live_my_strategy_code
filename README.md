# crypto_robot_live_my_strategy_code
Implémentation Python de la stratégie Envelope de Crypto Robot

# description
Remarque importante : projet en cours de développement !

Ce projet propose une implémentation Python de la stratégie Envelope décrite par Crypto Robot (https://www.google.com/url?sa=t&rct=j&q=&esrc=s&source=web&cd=&cad=rja&uact=8&ved=2ahUKEwiTk4acscGAAxVQSfEDHZKECawQwqsBegQIExAF&url=https%3A%2F%2Fwww.youtube.com%2Fwatch%3Fv%3Dr0QsWRQYwlI&usg=AOvVaw3Kmf2ywEV5YvbDptSu0wjV&opi=89978449)

Répertoire 'my_strategies_live' :
Dans ce répertoire se trouvent deux scripts .py. Le premier implémente la stratégie pour une paire.
Le second implémente la stratégie pour de multiples paires et propose en plus la gestion d'un stop loss

Répertoire 'my_strategies_backtest' :
Contient du code draft mais rien qui marche aujourd'hui -> ne pas en tenir compte

# installation
Le code nécessite un certain nombre de librairies, à installer séparément :
- os
- sys
- ta
- datetime
- json
- uuid
- logging
- ccxt
- pandas
- time
- numpy

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
