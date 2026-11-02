# ReproFlake issues found by Flakebait (draft for the ReproFlake maintainers)

Found while selecting flaky tests for Flakebait (Oct 2026). Section A lists defects we confirmed in the dataset or
its tooling. Section B lists entries whose recorded behavior we could not reproduce; our environment differs from
ReproFlake's (Apple M1 / arm64, `maven:3.8.6-eclipse-temurin-*` images instead of `maven:3.8.6-openjdk-*`,
networking disabled, Maven offline), so these need checking on ReproFlake's reference setup before they are
called bugs. The full per-candidate log is `reports/milestone1/selection_log.csv` (every check, in order).

## A. Confirmed defects

### A1. Custom OD Surefire crashes on any run without `-Dtest`
ReproFlake's OD environment uses a custom Surefire (TestingResearchIllinois/maven-surefire, commit `e44303cf`,
shipped in each OD archive's `.m2`). Any Maven invocation without `-Dtest` (a whole-module `mvn test`) dies with a
`NullPointerException` in `SurefirePlugin.getTest()`. ReproFlake's own reproduction scripts always pass `-Dtest`, so
they are unaffected, but anyone running a module's full suite (as a CI or a developer would) cannot. Our fix: two
null guards, `docker/od-surefire-null-test.patch`. Affects all 126 OD entries.

### A2. Archive without a cached Maven repository
`quickcheckbfc` (NIO): `Flakym2` is empty, so the project cannot build offline.

### A3. Cached Maven repositories missing artifacts needed to build offline
| category | result_container | detail |
|---|---|---|
| TD | HDFS-15702 | [ERROR] Failed to execute goal on project hadoop-hdfs: Could not resolve dependencies for project or |
| TD | YARN-9768 | [ERROR] Failed to execute goal on project hadoop-yarn-server-resourcemanager: Could not resolve depe |
| ID | graylog2servergraylog2serverf169d54serializeInteger | [ERROR] Failed to execute goal com.github.eirslett:frontend-maven-plugin:1.8.0:install-node-and-yarn |
| ID | graylog2servergraylog2server27269f2summarizeUsersReturnsListOfUsersIfCurrentUserIsNull | [ERROR] Failed to execute goal com.github.eirslett:frontend-maven-plugin:1.8.0:install-node-and-yarn |
| ID | hiveserdea6e13c9testLazyBinaryColumnarSerDeWithEmptyBinary | [ERROR] Failed to execute goal on project hive-serde: Could not resolve dependencies for project org |
| ID | graylog2servergraylog2server27269f2summarizeUsersReturnsListOfUsersWithoutTheCurrent | [ERROR] Failed to execute goal com.github.eirslett:frontend-maven-plugin:1.8.0:install-node-and-yarn |
| ID | graylog2servergraylog2server1ab626ctestNormalize | [ERROR] Failed to execute goal com.github.eirslett:frontend-maven-plugin:1.8.0:install-node-and-yarn |
| ID | hiveserdea6e13c9testBinarySortableSerDe | [ERROR] Failed to execute goal on project hive-serde: Could not resolve dependencies for project org |
| ID | graylog2servergraylog2serverf169d54serializeFloat | [ERROR] Failed to execute goal com.github.eirslett:frontend-maven-plugin:1.8.0:install-node-and-yarn |

`graylog2-server` entries need `frontend-maven-plugin` to download Node.js, which is not in the archive; the
Hadoop/Hive entries are missing dependencies of upstream modules.

### A4. Index labels
- One index row is labelled `britle`; the paper counts it as OD (we do too).
- Project names mix repository names, JIRA keys (`HDFS-15702`, `SCB-2731`) and commit-hash suffixes
  (`quickcheckc1c`, `ormlitecore59309e`), so entries from the same upstream repository are hard to group. A
  `repository` column (the URL is already in `flaky_info.txt`) would help; our mapping is
  `config/project_aliases.yaml`.

## B. Could not reproduce in our environment (needs checking on the reference setup)

### B1. `Fixed.patch` does not make the failing configuration pass (25 entries)
Applied cleanly, but the failing configuration still failed (most on the first of 20 runs).

| category | result_container | detail |
|---|---|---|
| TD | CAMEL-12025-testTo | fixed version passed 0/1 under the failing configuration |
| TD | CAMEL-12025-testMultipleSubscriptionsWithTimer | fixed version passed 0/1 under the failing configuration |
| TD | CAMEL-12025-testFromStreamTimer | fixed version passed 0/1 under the failing configuration |
| TD | CAMEL-12025-testToFunctionWithExchange | fixed version passed 0/1 under the failing configuration |
| TD | CAMEL-12025-testFrom | fixed version passed 0/1 under the failing configuration |
| TD | CAMEL-12025-testToFunction | fixed version passed 0/1 under the failing configuration |
| TD | HADOOP-12181 | fixed version passed 0/1 under the failing configuration |
| TD | CAMEL-12025-testToWithExchange | fixed version passed 0/1 under the failing configuration |
| NIO | quickcheckc1c35 | fixed version passed 0/1 under the failing configuration |
| OD | wildflynaming3a83b7b10 | fixed version passed 0/1 under the failing configuration |
| OD | wildflynaming3a83b7b4 | fixed version passed 0/1 under the failing configuration |
| OD | wildflynaming3a83b7b21 | fixed version passed 0/1 under the failing configuration |
| OD | wildflynaming3a83b7b15 | fixed version passed 0/1 under the failing configuration |
| OD | wildflynaming3a83b7b20 | fixed version passed 0/1 under the failing configuration |
| OD | wildflynaming3a83b7b7 | fixed version passed 0/1 under the failing configuration |
| OD | wildflynaming3a83b7b1 | fixed version passed 0/1 under the failing configuration |
| OD | wildflynaming3a83b7b2 | fixed version passed 0/1 under the failing configuration |
| OD | wildflynaming3a83b7b13 | fixed version passed 0/1 under the failing configuration |
| OD | wildflynaming3a83b7b14 | fixed version passed 0/1 under the failing configuration |
| OD | ormlitecore59309e17 | fixed version passed 0/1 under the failing configuration |
| ID | commonscollections9582007testBidiKeySetValuesOrder | fixed version passed 0/1 under the failing configuration |
| ID | cloudstackpluginsnetworkelementsniciranvp2bb182ctestExecuteLiveLockWhenControllerAllowsLoginAndFollo | fixed version passed 9/10 under the failing configuration |
| ID | fastjson8d94a61testForIssue20 | fixed version passed 0/1 under the failing configuration |
| ID | hopcore25508detestNewDocumentXml | fixed version passed 0/1 under the failing configuration |
| ID | cloudstackpluginsnetworkelementsniciranvp2bb182ctestExecuteTwoConsecutiveUnauthorizedExecutions | fixed version passed 4/5 under the failing configuration |

### B2. Failing configuration does not fail (48 entries; 44 ID)
For ID, NonDex 2.1.1 with the stored seed, victim only. Hash-iteration orders can differ across JVM builds and
architectures, so the stored seed may not trigger the failure on our JVMs.

| category | result_container | detail |
|---|---|---|
| TD | CAMEL-15580 | failing configuration failed 0/1 |
| TD | CAMEL-17188 | failing configuration failed 11/12 |
| TD | BOOKKEEPER-709 | delay patch does not apply |
| OD | dubbodubborpcdubborpcdubbo5ea6b331 | failing configuration failed 0/1 |
| ID | wildflyundertowd2ec064testRuntime10 | failing configuration failed 1/2 |
| ID | feigncore15cf841realizingSimpleClassMultipleGenericThirdLevel5 | failing configuration failed 0/1 |
| ID | commonkafkacommonkafkad787351fail_offsetPositionBeforeFailedRecord | failing configuration failed 4/5 |
| ID | elideelidecore5c39308testHiddenFields | failing configuration failed 0/1 |
| ID | quarkusindependentprojectstoolsregistryclient291e830testRegistryMavenRepoUrlAndId | failing configuration failed 0/1 |
| ID | vjtoolsvjkit2d3ca35jsonp | failing configuration failed 4/5 |
| ID | wildflyundertowd2ec064testRuntime1 | failing configuration failed 2/3 |
| ID | nifinifinarbundlesnifistandardservicesnifihbase_2clientservicebundlenifihbase_2clientservice531a9det | failing configuration failed 0/1 |
| ID | elideelidecore80439b6writeListIncluded | failing configuration failed 0/1 |
| ID | feignjsonf21d32aencodesArray | failing configuration failed 0/1 |
| ID | feigncore15cf841overridingConcreteSimpleClassGenericSecondLevel | failing configuration failed 0/1 |
| ID | jacksondataformatsbinaryprotobuf0eeb08ctestSimpleLongAscii | failing configuration failed 0/1 |
| ID | Stratamodulesdatadc3ebb8of_addition | failing configuration failed 0/1 |
| ID | incubatorshardingsphereshardingjdbcshardingjdbccorea0ffcf0assertInsertWithBatchExecute | failing configuration failed 0/1 |
| ID | fastjson2codegentestcda9e5dtest1 | failing configuration failed 1/2 |
| ID | hapifhirhapifhirstructuresdstu2443b59atestSearchByPostUseJson7 | failing configuration failed 0/1 |
| ID | jsonschemacore43fda7dtoStringTest | failing configuration failed 0/1 |
| ID | servicecombjavachassiscommoncommonrest94a672fshould_failed_when_not_defined_any_schema | failing configuration failed 0/1 |
| ID | appenginepluginscoreca26908testCall_withOverrideComponents | failing configuration failed 0/1 |
| ID | cloudstackpluginsnetworkelementsniciranvp2bb182ctestExecuteUnauthorizedThenSuccess | failing configuration failed 11/12 |
| ID | XChangexchangekrakenc7dd935testAdaptTradeHistoryByCurrencyPair | failing configuration failed 0/1 |
| ID | ignite3modulestable19c8a82testGetTableDuringCreation | failing configuration failed 0/1 |
| ID | OpenRefinemaina195e4etestGuessTypes | failing configuration failed 0/1 |
| ID | jolokiasupportspring275165bsystemProperties | failing configuration failed 0/1 |
| ID | ignite3modulestable19c8a82testApiTableManagerOnStop | failing configuration failed 0/1 |
| ID | ecchronoscore5555108testPartiallyRepaired | failing configuration failed 0/1 |
| ID | hutoolhutoolcore33121a4scanMetaAnnotationTest | failing configuration failed 4/5 |
| ID | oktahookssdkjavahooks9187787passwordImportUnverifiedTest | failing configuration failed 0/1 |
| ID | wildflyundertowd2ec064testRuntime2 | failing configuration failed 0/1 |
| ID | jsonschemavalidator0c2a855testCollectorContextWithKeyword | failing configuration failed 0/1 |
| ID | pac4jpac4joauth077c12ftestToJSONString | failing configuration failed 0/1 |
| ID | cloudstackutils4c5a2basetMailRecipientsTest | failing configuration failed 9/10 |
| ID | servicecombjavachassisfoundationsfoundationvertxf37cdb1setParameter | failing configuration failed 0/1 |
| ID | shenyushenyuadmin02696b4testRuleHandler4 | failing configuration failed 0/1 |
| ID | wildflyundertowd2ec064testRuntime4 | failing configuration failed 0/1 |
| ID | jacksondatabindebe71f8testAddFilterWithEmptyStringId | failing configuration failed 0/1 |
| ID | jacksondataformatsbinaryprotobuf0eeb08ctestReadPointLong | failing configuration failed 0/1 |
| ID | SCB-2692-TestStandardHttpServletRequestEx | failing configuration failed 0/1 |
| ID | feigncore15cf841OverridingConcreteSimpleClassGenericThirdLevel1 | failing configuration failed 0/1 |
| ID | undertowservletc33cf56testParametersFromOriginalPostRequest | failing configuration failed 1/2 |
| ID | quarkusindependentprojectstoolscodestarts8f7119echeckDefaultProject | failing configuration failed 0/1 |
| ID | OpenRefinemaina68ba3btestSelectedEmptyChoice | failing configuration failed 0/1 |
| ID | apolloapolloadminservicea882f3etestReleaseBuild | failing configuration failed 14/15 |
| ID | avrolangjavaavro7fd098atestRecord | failing configuration failed 0/1 |

### B3. Passing configuration does not pass (6 entries)

| category | result_container | detail |
|---|---|---|
| TD | YARN-1268 | passing configuration passed 0/1 |
| OD | wildflynaming3a83b7b17 | passing configuration passed 0/1 |
| OD | wildflynaming3a83b7b16 | passing configuration passed 0/1 |
| ID | ignite3modulesstoragerocksdb19c8a82testRowSerialization | passing configuration passed 0/1 |
| ID | biojavabiojavastructure65ad15ftestAtomCacheNameParsing | passing configuration passed 0/1 |
| ID | fastjson833fe42test_cast_to_Timestamp_1970_01_01_00_00_00 | passing configuration passed 0/1 |
