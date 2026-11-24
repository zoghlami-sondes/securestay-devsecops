# Dossier de preuves avant et après correction

Pour la soutenance, associer chaque preuve au commit ou au build d'origine, à la date, au rôle utilisé et au résultat observé. Utiliser les rapports historiques validés et des extraits expurgés. Conserver uniquement les métadonnées utiles, sans session, mot de passe, corps HTTP ni valeur sensible.

| Contrôle | Preuve avant à joindre | Preuve après produite par le pipeline |
| --- | --- | --- |
| Accès au profil d'un autre compte (IDOR) | Rapport historique établissant qu'un compte de test ordinaire accédait au profil d'un autre compte. | `session_profile=true`, `session_bookings=true` et `idor_denied=true` dans le JSON ZAP passif. Le contrôle d'accès doit renvoyer 403. |
| Validation des prix non finis | Rapport ou test dynamique historique établissant que la route de recherche acceptait une borne non finie. | `non_finite_price_rejected=true` dans le JSON. La route doit renvoyer 400. |

Un résultat après correction ne remplace pas une preuve avant correction. Si la preuve historique d'une des deux lignes manque, la ligne correspondante reste non démontrée. Les rapports de conformité du build conservent également le digest, les verdicts réseau et les alertes ZAP par identifiant et gravité.
