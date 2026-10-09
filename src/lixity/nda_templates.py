"""Plain-language confidentiality agreements for project review and collaboration.

These original templates preserve mandatory disclosure rights and do not claim
universal enforceability. Interface language does not select a country's law.
Only the requested document fields are substituted.
"""

NDA_TEMPLATES: dict[str, str] = {
    "en": """Confidentiality agreement

Project: {{project_title}}
Recipient: {{recipient_name}}
Address: {{recipient_address}}
Date: {{date}}
Place: {{place}}

What we share
For project review or collaboration, we may share non-public drafts, research,
notes, ideas and other materials, including copies. Information is confidential
if marked or reasonably recognizable as such, whether shared in writing,
orally, visually or electronically.

How we use it
Use this information only to review or collaborate on the project. Take
reasonable care and make only necessary copies. Give access only to people
who need it and have equivalent confidentiality duties or professional secrecy.

Sharing, publishing or uploading it to external services needs the project
representative's permission, subject to the exceptions below. Approved tools
remain allowed.

Exceptions and protected rights
These duties do not cover information that becomes public without a breach,
was lawfully known without confidentiality duties, was developed independently
without using confidential information, was lawfully received from an
unrestricted third party or was expressly released.

Legally required or protected disclosures, protected reports of wrongdoing
and access to authorities remain allowed. Protected reporting needs no
permission or prior notice. Mandatory rights, including lawful employee and
employee-representative rights, remain unaffected. You may seek confidential
legal or professional advice.

Rights stay with their owners
Ownership, copyright and other rights stay with their holders. This agreement
permits only the use needed for project review or collaboration. It grants no
publication rights, ownership transfer, exclusive license or rights in
third-party materials.

Return or deletion
On request or when the review or collaboration ends, return or delete
confidential copies within a reasonable time. Keep legally required copies
and copies held solely as legal evidence restricted. Routine backups may
remain until normal deletion, without use for another purpose.
Confidentiality duties continue for copies lawfully retained.

What else applies
Applicable legal rules govern liability and remedies. Mandatory protections
remain in place. This agreement adds no contractual penalty or blanket liability
without fault. We agree any changes together.

Recipient: {{recipient_name}}
Signature ______________________________________________________________
Project representative: {{project_author}}
Signature ______________________________________________________________
""",
    "de": """Vertraulichkeitsvereinbarung

Projekt: {{project_title}}
Empfangende Person: {{recipient_name}}
Anschrift: {{recipient_address}}
Datum: {{date}}
Ort: {{place}}

Was wir miteinander teilen
Für die Prüfung oder Zusammenarbeit am Projekt können wir nicht öffentliche
Entwürfe, Recherchen, Notizen, Ideen und andere Unterlagen einschließlich Kopien
teilen. Vertraulich sind Informationen, die so gekennzeichnet oder nach Inhalt
und Umständen vernünftigerweise als vertraulich erkennbar sind. Das gilt für
schriftliche, mündliche, bildliche und elektronische Mitteilungen.

Wie wir damit umgehen
Nutzen Sie diese Informationen nur für die Prüfung oder Zusammenarbeit am
Projekt. Gehen Sie sorgfältig damit um und fertigen Sie nur notwendige Kopien
an. Zugriff erhalten nur Personen, die ihn benötigen und gleichwertig zur
Geheimhaltung oder beruflich zur Verschwiegenheit verpflichtet sind.

Für Weitergabe, Veröffentlichung oder Hochladen in externe Dienste brauchen
Sie die Erlaubnis der projektverantwortlichen Person. Die folgenden Ausnahmen
bleiben unberührt. Freigegebene Werkzeuge dürfen Sie weiter nutzen.

Ausnahmen und geschützte Rechte
Die Pflichten gelten nicht für Informationen, die ohne Verstoß gegen diese
Vereinbarung öffentlich sind oder werden, Ihnen bereits rechtmäßig ohne
Geheimhaltungspflicht bekannt waren, unabhängig ohne vertrauliche Informationen
entwickelt wurden, von einer anderen Person rechtmäßig ohne Geheimhaltungspflicht
weitergegeben oder ausdrücklich freigegeben wurden.

Gesetzlich gebotene oder geschützte Offenlegungen, geschützte Meldungen von
Fehlverhalten und der Zugang zu Behörden bleiben erlaubt. Geschützte Meldungen
brauchen weder Erlaubnis noch Vorabinformation. Zwingende Rechte, auch die von
Beschäftigten und Arbeitnehmervertretungen, bleiben unberührt. Vertrauliche
rechtliche oder fachliche Beratung dürfen Sie in Anspruch nehmen.

Die Rechte bleiben bei ihren Inhabern
Eigentum, Urheberrechte und andere Rechte bleiben bei ihren Inhabern. Diese
Vereinbarung erlaubt nur die für Prüfung oder Zusammenarbeit am Projekt
notwendige Nutzung. Sie räumt keine Veröffentlichungsrechte,
Eigentumsübertragungen, ausschließlichen Nutzungsrechte oder Rechte an
fremden Inhalten ein.

Zurückgeben oder löschen
Geben Sie vertrauliche Kopien auf Verlangen oder nach Ende der Prüfung oder
Zusammenarbeit innerhalb angemessener Frist zurück oder löschen Sie sie.
Gesetzlich erforderliche oder ausschließlich zu Beweiszwecken aufbewahrte
Kopien bleiben zugriffsbeschränkt. Sicherungskopien dürfen bis zur üblichen
Löschung bestehen, ohne Nutzung für andere Zwecke. Für erlaubterweise
aufbewahrte Kopien gelten die Geheimhaltungspflichten weiter.

Was außerdem gilt
Für Haftung und Rechtsfolgen gelten die anwendbaren gesetzlichen Regeln.
Diese Vereinbarung enthält keine Vertragsstrafe und keine pauschale Haftung ohne
Verschulden.
Gesetzliche Schutzrechte bleiben erhalten. Änderungen vereinbaren wir gemeinsam.

Empfangende Person: {{recipient_name}}
Unterschrift ___________________________________________________________
Projektverantwortliche Person: {{project_author}}
Unterschrift ___________________________________________________________
""",
    "fr": """Accord de confidentialité

Projet : {{project_title}}
Destinataire : {{recipient_name}}
Adresse : {{recipient_address}}
Date : {{date}}
Lieu : {{place}}

Ce que nous partageons
Pour examiner le projet ou y collaborer, nous pouvons partager des brouillons,
recherches, notes, idées et autres éléments non publics, ainsi que leurs copies.
Les informations sont confidentielles si elles sont signalées ou raisonnablement
reconnaissables comme telles, à l'écrit, à l'oral, sous forme visuelle ou
électronique.

Comment les utiliser
Utilisez ces informations uniquement pour examiner le projet ou y collaborer.
Prenez-en raisonnablement soin et ne faites que les copies nécessaires.
Réservez l'accès aux personnes qui en ont besoin et sont tenues à une
confidentialité équivalente ou au secret professionnel.

Pour les partager, les publier ou les charger dans des services externes,
demandez l'autorisation du responsable du projet, sous réserve des exceptions
ci-dessous. Les outils approuvés restent permis.

Exceptions et droits protégés
Ces obligations ne couvrent pas les informations devenues publiques sans
violation, légalement connues sans obligation de confidentialité, développées
indépendamment sans utiliser d'informations confidentielles, légalement reçues
d'un tiers libre de restrictions ou expressément libérées.

Les divulgations imposées ou protégées par la loi, les signalements protégés
de comportements répréhensibles et l'accès aux autorités restent permis.
Les signalements protégés ne nécessitent ni autorisation ni notification
préalable. Les droits impératifs, y compris ceux des salariés et de leurs
représentants, restent préservés. Vous pouvez demander un conseil juridique
ou professionnel confidentiel.

Les droits restent à leurs titulaires
La propriété, les droits d'auteur et les autres droits restent à leurs
titulaires. Cet accord permet uniquement l'utilisation nécessaire à l'examen
du projet ou à la collaboration. Il n'accorde aucun droit de publication,
transfert de propriété, licence exclusive ou droit sur les éléments de tiers.

Restituer ou supprimer
Sur demande ou à la fin de l'examen ou de la collaboration, restituez ou
supprimez les copies confidentielles dans un délai raisonnable. Gardez un
accès limité aux copies imposées par la loi ou conservées uniquement comme
preuve juridique. Les sauvegardes peuvent subsister jusqu'à leur suppression
normale, sans autre utilisation. Les obligations de confidentialité continuent
pour les copies légalement conservées.

Ce qui s'applique aussi
Les règles légales applicables régissent la responsabilité et les recours.
Les protections obligatoires restent en vigueur. Cet accord n'ajoute aucune
pénalité contractuelle ni responsabilité générale sans faute. Nous convenons
ensemble de toute modification.

Destinataire : {{recipient_name}}
Signature ______________________________________________________________
Responsable du projet : {{project_author}}
Signature ______________________________________________________________
""",
    "es": """Acuerdo de confidencialidad

Proyecto: {{project_title}}
Persona destinataria: {{recipient_name}}
Dirección: {{recipient_address}}
Fecha: {{date}}
Lugar: {{place}}

Lo que compartimos
Para revisar el proyecto o colaborar en él, podemos compartir borradores,
investigaciones, notas, ideas y otros materiales no públicos, incluidas las
copias. La información es confidencial si está identificada o es razonablemente
reconocible como tal, por escrito, de forma oral, visual o electrónica.

Cómo utilizarlo
Utilice esta información solo para revisar el proyecto o colaborar en él.
Trátela con cuidado razonable y haga solo las copias necesarias. Dé acceso
únicamente a quienes lo necesitan y tienen deberes equivalentes de
confidencialidad o secreto profesional.

Compartirla, publicarla o cargarla en servicios externos requiere el permiso
del responsable del proyecto, con las excepciones siguientes. Las herramientas
aprobadas siguen permitidas.

Excepciones y derechos protegidos
Estos deberes no cubren información que se haga pública sin incumplimiento,
se conozca lícitamente sin deberes de confidencialidad, se desarrolle de forma
independiente sin utilizar información confidencial, se reciba lícitamente de
un tercero sin restricciones o se libere expresamente.

Las divulgaciones exigidas o protegidas por ley, las comunicaciones protegidas
de irregularidades y el acceso a las autoridades siguen permitidos. Las
comunicaciones protegidas no requieren permiso ni aviso previo. Los derechos
imperativos, incluidos los de los trabajadores y sus representantes, no se
restringen. Puede solicitar asesoramiento jurídico o profesional confidencial.

Los derechos siguen con sus titulares
La propiedad, los derechos de autor y los demás derechos permanecen con sus
titulares. Este acuerdo solo permite el uso necesario para revisar el proyecto
o colaborar en él. No concede derechos de publicación, transmisiones de
propiedad, licencias exclusivas ni derechos sobre materiales de terceros.

Devolver o eliminar
A petición o al terminar la revisión o colaboración, devuelva o elimine las
copias confidenciales dentro de un plazo razonable. Mantenga un acceso restringido
a las copias exigidas por ley o conservadas únicamente como prueba jurídica.
Las copias de seguridad pueden permanecer hasta su eliminación normal, sin
otros usos. Los deberes de confidencialidad continúan para las copias
conservadas lícitamente.

Qué más se aplica
Las normas legales aplicables rigen la responsabilidad y las medidas de
reparación. Este acuerdo no añade penalizaciones contractuales ni responsabilidad
general sin culpa. Las protecciones legales obligatorias se mantienen. Acordamos
los cambios entre ambas partes.

Persona destinataria: {{recipient_name}}
Firma __________________________________________________________________
Responsable del proyecto: {{project_author}}
Firma __________________________________________________________________
""",
    "it": """Accordo di riservatezza

Progetto: {{project_title}}
Destinatario/a: {{recipient_name}}
Indirizzo: {{recipient_address}}
Data: {{date}}
Luogo: {{place}}

Cosa condividiamo
Per esaminare il progetto o collaborarvi, possiamo condividere bozze, ricerche,
appunti, idee e altri materiali non pubblici, incluse le copie. Le informazioni
sono riservate se indicate o ragionevolmente riconoscibili come tali, per
iscritto, a voce, in forma visiva o elettronica.

Come usarle
Usa queste informazioni solo per esaminare il progetto o collaborarvi.
Trattale con ragionevole diligenza e fai solo le copie necessarie. Consenti
l'accesso soltanto a chi ne ha bisogno ed è tenuto a una riservatezza equivalente
o al segreto professionale.

Condividerle, pubblicarle o caricarle su servizi esterni richiede il permesso
del responsabile del progetto, con le eccezioni seguenti. Gli strumenti
approvati restano consentiti.

Eccezioni e diritti protetti
Questi obblighi non riguardano informazioni rese pubbliche senza violazioni,
lecitamente note senza obblighi di riservatezza, sviluppate indipendentemente
senza usare informazioni riservate, ricevute lecitamente da un terzo senza
restrizioni o espressamente liberate.

Restano consentite le divulgazioni richieste o protette dalla legge, le
segnalazioni protette di illeciti e l'accesso alle autorità. Le segnalazioni
protette non richiedono permesso né preavviso. I diritti inderogabili, inclusi
quelli dei lavoratori e dei loro rappresentanti, non sono limitati. Puoi
richiedere una consulenza legale o professionale riservata.

I diritti rimangono ai titolari
La proprietà, i diritti d'autore e gli altri diritti rimangono ai loro titolari.
Questo accordo permette solo l'uso necessario per esaminare il progetto o
collaborarvi. Non concede diritti di pubblicazione, trasferimenti di proprietà,
licenze esclusive o diritti sui materiali di terzi.

Restituire o cancellare
Su richiesta o al termine dell'esame o della collaborazione, restituisci o
cancella le copie riservate entro un periodo ragionevole. Mantieni un accesso
limitato alle copie richieste dalla legge o conservate solo come prova giuridica.
Le copie di sicurezza possono rimanere fino alla cancellazione ordinaria, senza
altri usi. Gli obblighi di riservatezza continuano per le copie conservate
lecitamente.

Cos'altro si applica
Le regole legali applicabili disciplinano la responsabilità e i rimedi.
Le tutele obbligatorie restano valide. Questo accordo non aggiunge penali
contrattuali né responsabilità generale senza colpa. Concordiamo insieme
eventuali modifiche.

Destinatario/a: {{recipient_name}}
Firma __________________________________________________________________
Responsabile del progetto: {{project_author}}
Firma __________________________________________________________________
""",
    "pt": """Acordo de confidencialidade

Projeto: {{project_title}}
Pessoa destinatária: {{recipient_name}}
Endereço: {{recipient_address}}
Data: {{date}}
Local: {{place}}

O que partilhamos
Para analisar o projeto ou colaborar nele, podemos partilhar versões
preliminares, pesquisas, notas, ideias e outros materiais não públicos,
incluindo cópias. As informações são confidenciais se identificadas ou
razoavelmente reconhecíveis como tal, por escrito, oralmente, visualmente
ou por meios eletrónicos.

Como utilizar
Utilize estas informações apenas para analisar o projeto ou colaborar nele.
Trate-as com cuidado razoável e faça apenas as cópias necessárias. Dê acesso
só a quem dele necessita e tem deveres equivalentes de confidencialidade ou
segredo profissional.

Partilhar, publicar ou enviar para serviços externos exige autorização do
responsável pelo projeto, com as exceções seguintes. As ferramentas aprovadas
continuam permitidas.

Exceções e direitos protegidos
Estes deveres não abrangem informações tornadas públicas sem violação,
conhecidas licitamente sem deveres de confidencialidade, desenvolvidas de
forma independente sem utilizar informações confidenciais, recebidas
licitamente de um terceiro sem restrições ou expressamente liberadas.

As divulgações exigidas ou protegidas por lei, as comunicações protegidas de
irregularidades e o acesso às autoridades continuam permitidos. As comunicações
protegidas não exigem autorização nem aviso prévio. Os direitos imperativos,
incluindo os dos trabalhadores e dos seus representantes, não são limitados.
Pode procurar aconselhamento jurídico ou profissional confidencial.

Os direitos permanecem com os titulares
A propriedade, os direitos de autor e os demais direitos permanecem com os
respetivos titulares. Este acordo permite apenas a utilização necessária para
analisar o projeto ou colaborar nele. Não concede direitos de publicação,
transferências de propriedade, licenças exclusivas ou direitos sobre materiais
de terceiros.

Devolver ou eliminar
A pedido ou no fim da análise ou colaboração, devolva ou elimine as cópias
confidenciais num prazo razoável. Mantenha acesso restrito às cópias exigidas
por lei ou conservadas apenas como prova jurídica. As cópias de segurança podem
permanecer até à eliminação normal, sem outros usos. Os deveres de
confidencialidade continuam para as cópias conservadas licitamente.

O que mais se aplica
As regras legais aplicáveis regem a responsabilidade e as medidas de reparação.
As proteções legais obrigatórias mantêm-se. Este acordo não acrescenta
penalizações contratuais nem responsabilidade geral sem culpa. Acordamos
as alterações entre ambas as partes.

Pessoa destinatária: {{recipient_name}}
Assinatura _____________________________________________________________
Responsável pelo projeto: {{project_author}}
Assinatura _____________________________________________________________
""",
    "nl": """Geheimhoudingsovereenkomst

Project: {{project_title}}
Ontvanger: {{recipient_name}}
Adres: {{recipient_address}}
Datum: {{date}}
Plaats: {{place}}

Wat we delen
Voor projectbeoordeling of samenwerking kunnen we niet-openbare concepten,
onderzoek, notities, ideeën en ander materiaal delen, inclusief kopieën.
Informatie is vertrouwelijk als dit is aangegeven of redelijkerwijs herkenbaar
is, schriftelijk, mondeling, visueel of elektronisch.

Hoe we het gebruiken
Gebruik deze informatie alleen om het project te beoordelen of eraan samen
te werken. Ga er redelijk zorgvuldig mee om en maak alleen noodzakelijke
kopieën. Geef alleen toegang aan mensen die deze nodig hebben en gelijkwaardige
geheimhoudingsplichten hebben of aan een beroepsgeheim gebonden zijn.

Delen, publiceren of uploaden naar externe diensten vereist toestemming van de
projectverantwoordelijke, met de uitzonderingen hieronder. Goedgekeurde
hulpmiddelen blijven toegestaan.

Uitzonderingen en beschermde rechten
Deze plichten gelden niet voor informatie die zonder schending openbaar wordt,
rechtmatig bekend was zonder geheimhoudingsplicht, onafhankelijk zonder
vertrouwelijke informatie is ontwikkeld, rechtmatig van een derde zonder
beperkingen is ontvangen of uitdrukkelijk is vrijgegeven.

Wettelijk verplichte of beschermde openbaarmaking, beschermde meldingen van
misstanden en toegang tot autoriteiten blijven toegestaan. Beschermde meldingen
vereisen geen toestemming of voorafgaande kennisgeving. Dwingende rechten,
ook die van werknemers en hun vertegenwoordigers, blijven behouden.
Je mag vertrouwelijk juridisch of professioneel advies vragen.

De rechten blijven bij hun houders
Eigendom, auteursrechten en andere rechten blijven bij hun rechthebbenden.
Deze overeenkomst staat alleen het gebruik toe dat nodig is voor beoordeling
of samenwerking aan het project. Zij verleent geen publicatierechten,
eigendomsoverdracht, exclusieve licentie of rechten op materiaal van derden.

Teruggeven of verwijderen
Geef op verzoek of na afloop van de beoordeling of samenwerking vertrouwelijke
kopieën binnen een redelijke termijn terug of verwijder ze. Houd wettelijk
vereiste kopieën en kopieën die uitsluitend als juridisch bewijs worden bewaard
beperkt toegankelijk. Reservekopieën mogen tot de gebruikelijke verwijdering
blijven bestaan, zonder ander gebruik. De geheimhoudingsplichten blijven gelden
voor rechtmatig bewaarde kopieën.

Wat verder geldt
De toepasselijke wettelijke regels bepalen aansprakelijkheid en rechtsmiddelen.
Verplichte wettelijke bescherming blijft gelden. Deze overeenkomst voegt geen
contractuele boete of algemene aansprakelijkheid zonder schuld toe. Wij spreken
wijzigingen samen af.

Ontvanger: {{recipient_name}}
Handtekening ___________________________________________________________
Projectverantwoordelijke: {{project_author}}
Handtekening ___________________________________________________________
""",
}

NDA_DOCUMENT_LABELS: dict[str, dict[str, str]] = {
    "en": {"title": "Confidentiality agreement"},
    "de": {"title": "Vertraulichkeitsvereinbarung"},
    "fr": {"title": "Accord de confidentialité"},
    "es": {"title": "Acuerdo de confidencialidad"},
    "it": {"title": "Accordo di riservatezza"},
    "pt": {"title": "Acordo de confidencialidade"},
    "nl": {"title": "Geheimhoudingsovereenkomst"},
}
