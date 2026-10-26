« Je veux rester pas trop loin de ma famille. » Jusqu'ici, le quiz de l'atlas écoutait mal cette réponse : elle modifiait des poids, jamais une distance. Un étudiant de Seine-et-Marne souhaitant rester proche de chez lui pouvait voir Nice sortir en tête — à près de 700 km de son domicile. Cette limite est corrigée : le quiz intègre désormais le domicile, calcule la distance vers chaque ville et filtre le classement à un rayon de 300 km quand la proximité est une priorité.

## Comment ça marche

1. **Question 0** : le quiz demande la commune de domicile et la géolocalise via l'API Geo ([api.gouv.fr](http://api.gouv.fr), coordonnées officielles).
2. **Distances géodésiques** : chaque ville du résultat affiche sa distance au domicile (formule haversine, rayon terrestre 6 371 km — une méthode standard et traçable).
3. **Filtre conditionnel** : si la réponse est « rester proche », seules les villes à moins de 300 km sont classées ; si le rayon contient moins de trois villes du panel, il est complété par les meilleures villes hors rayon, explicitement marquées. Les autres priorités (« découvrir une nouvelle région », « peu importe ») n'activent aucun filtre : la distance reste affichée pour information.

## Exemple : un terminal d'Île-de-France qui veut rester proche

Pour un domicile en Seine-et-Marne (77) avec priorité proximité :

| Ville | Distance | Note de risque |
| --- | --- | --- |
| Paris | \~35 km | C |
| Reims | \~100-120 km | C |
| Lille | \~200 km | B |
| Caen | \~215-235 km | B |
| Dijon | \~250-260 km | B |
| Nancy | \~245-270 km | B |
| Angers | \~280 km | B |
| Nice (exclue par le filtre) | \~670-690 km | C |

Le filtre change la lecture : ce n'est plus « la meilleure ville du panel », mais « la meilleure ville dans ton rayon ». Et la nuance apparaît en creux : Reims est la plus proche des villes bien classées du rayon mais porte la note C (pire score emploi du panel, 24,3) ; Paris, à 35 km, affiche un taux d'effort de 122,2 %. La proximité ne suffit pas. (Note de risque : A = aucun pilier sous 30 ni dernière place ; B = un pilier sous 30 ou une dernière place ; C = au moins deux piliers sous 30 ou score global sous 45 — un indicateur d'adéquation aux priorités de l'étudiant, pas un défaut de paiement.)

## La meilleure ville pour ton profil n'est pas la plus proche

Les tests du quiz illustrent le trade-off : depuis un domicile de Seine-et-Marne, avec un profil « budget serré + rester travailler sur place », Nancy (246 km) sort devant toutes les villes plus proches — parce que son logement (96,7) et sa démographie (81,7) dominent. À l'inverse, Paris à 35 km du domicile affiche un taux d'effort de 122,2 % : proche mais hors du budget type sans aide. La distance est une contrainte parmi d'autres, pas un critère qui écrase les autres.

## Limites de lecture

Le rayon de 300 km est un choix arbitré, documenté comme tel : il ne garantit ni un temps de trajet (une ville à 250 km mal desservie peut être moins « proche » qu'une ville TGV à 400 km) ni une fréquence de retour réaliste. La distance est géodésique « à vol d'oiseau », pas routière ou ferroviaire. Enfin, le filtre ne s'applique qu'aux 20 villes du panel — un rayon peut contenir des villes universitaires non mesurées par l'atlas.

<i>Teste ton propre cas : lance le quiz, entre ta commune à la question 0, et regarde comment ton rayon redessine le classement.</i>
