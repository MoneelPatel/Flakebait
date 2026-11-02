# Prompts for hand review

Check that no prompt names the mutated line or hints at flakiness. Automatic forbidden-term hits are listed under each prompt.

## repair-id-commonslang1163e17testReflectionHashCodeExcludeFields-L1-flaky

Mutated line (src/main/java/org/apache/commons/lang3/builder/HashCodeBuilder.java:897): `if (array != null) {`

Forbidden-term hits: none

## `ArrayUtilsTest` fails in `commons-lang`

The test `testHashCode` in `org.apache.commons.lang3.ArrayUtilsTest` is failing:

```
expected: not equal but was: <629>
```

You can reproduce it with:

```
mvn test -Dtest=ArrayUtilsTest
```

Please find the cause of this failure in the code and fix it.


## repair-id-commonslang1163e17testReflectionHashCodeExcludeFields-L2-flaky

Mutated line (src/main/java/org/apache/commons/lang3/builder/HashCodeBuilder.java:897): `if (array != null) {`

Forbidden-term hits: none

## `HashCodeBuilderTest` fails in `commons-lang`

The test `testObjectArrayAsObject` in `org.apache.commons.lang3.builder.HashCodeBuilderTest` is failing:

```
expected: <23273> but was: <629>
```

You can reproduce it with:

```
mvn test -Dtest=HashCodeBuilderTest
```

Please find the cause of this failure in the code and fix it.


## repair-id-nifinificommonsnifirecord7823156testAliasConflictingAliasValues-L1-flaky

Mutated line (nifi-commons/nifi-record/src/main/java/org/apache/nifi/serialization/record/MapRecord.java:163): `return null;`

Forbidden-term hits: none

## `TestDataTypeUtils` fails in `nifi-commons/nifi-record`

The test `testConvertRecordFieldToObject` in `org.apache.nifi.serialization.record.TestDataTypeUtils` is failing:

```
(no message)
```

You can reproduce it with:

```
mvn test -pl nifi-commons/nifi-record -Dtest=TestDataTypeUtils
```

Please find the cause of this failure in the code and fix it.


## repair-id-nifinificommonsnifirecord7823156testAliasConflictingAliasValues-L2-flaky

Mutated line (nifi-commons/nifi-record/src/main/java/org/apache/nifi/serialization/record/MapRecord.java:163): `return null;`

Forbidden-term hits: none

## `TestMapRecord` fails in `nifi-commons/nifi-record`

The test `testDefaultValueInGivenField` in `org.apache.nifi.serialization.record.TestMapRecord` is failing:

```
(no message)
```

You can reproduce it with:

```
mvn test -pl nifi-commons/nifi-record -Dtest=TestMapRecord
```

Please find the cause of this failure in the code and fix it.


## repair-id-pulsarpulsarclientc3292a6testKeyValueSchemaInfoToString-L1-flaky

Mutated line (pulsar-client/src/main/java/org/apache/pulsar/client/impl/schema/KeyValueSchemaInfo.java:164): `;`

Forbidden-term hits: none

## `MessageImplTest` fails in `pulsar-client`

The test `testSeparatedAVROVersionGetProducerDataAssigned` in `org.apache.pulsar.client.impl.MessageImplTest` is failing:

```
Name is null
```

You can reproduce it with:

```
mvn test -pl pulsar-client -Dtest=MessageImplTest
```

Please find the cause of this failure in the code and fix it.


## repair-id-pulsarpulsarclientc3292a6testKeyValueSchemaInfoToString-L2-flaky

Mutated line (pulsar-client/src/main/java/org/apache/pulsar/client/impl/schema/KeyValueSchemaInfo.java:164): `;`

Forbidden-term hits: none

## `KeyValueSchemaInfoTest` fails in `pulsar-client`

The test `encodeDecodeNestedKeyValueSchemaInfo` in `org.apache.pulsar.client.impl.schema.KeyValueSchemaInfoTest` is failing:

```
expected [SEPARATED] but found [INLINE]
```

You can reproduce it with:

```
mvn test -pl pulsar-client -Dtest=KeyValueSchemaInfoTest
```

Please find the cause of this failure in the code and fix it.


## repair-nio-quickcheck4862-L1-flaky

Mutated line (core/src/main/java/com/pholser/junit/quickcheck/internal/generator/GeneratorRepository.java:406): `;`

Forbidden-term hits: none

## `ComponentizedGeneratorsIsolateConfigurationFromComponentsTest` fails in `core`

The test `boxOfFoo` in `com.pholser.junit.quickcheck.ComponentizedGeneratorsIsolateConfigurationFromComponentsTest` is failing:

```
Expected: has 0 failures
     but: was <
Time: 0.002
There was 1 failure:
1) holds(com.pholser.junit.quickcheck.ComponentizedGeneratorsIsolateConfigurationFromComponentsTest$BoxOfFoo)
java.lang.IndexOutOfBoundsException: Index: 0, Size: 0
 at java.util.ArrayList.rangeCheck(ArrayList.java:659)
 at java.util.ArrayList.get(ArrayList.java:435)
 at java.util.Collections$UnmodifiableList.get(Collections.java:1311)
 at com.pholser.junit.quickcheck.test.generator.ABox.generate(ABox.java:45)
 at com.pholser.junit.quickcheck.test.generator.ABox.generate(ABox.java:33)
 at com.pholser.junit.quickcheck.internal.generator.PropertyParameterGenerationContext.generate(PropertyParameterGenerationContext.java:84)
 at com.pholser.junit.quickcheck.internal.SeededValue.<init>(SeededValue.java:37)
 at java.util.stream.ReferencePipeline$3$1.accept(ReferencePipeline.java:193)
 at java.util.ArrayList$ArrayListSpliterator.forEachRemaining(ArrayList.java:1384)
 at java.util.stream.AbstractPipeline.copyInto(AbstractPipeline.java:482)
 at java.util.stream.AbstractPipeline.wrapAndCopyInto(AbstractPipeline.java:472)
 at java.util.stream.ReduceOps$ReduceOp.evaluateSequential(ReduceOps.java:708)
 at java.util.stream.AbstractPipeline.evaluate(AbstractPipeline.java:234)
 at java.util.stream.ReferencePipeline.collect(ReferencePipeline.java:566)
 at com.pholser.junit.quickcheck.internal.sampling.TupleParameterSampler.lambda$sample$0(TupleParameterSampler.java:67)
 at java.util.stream.StreamSpliterators$InfiniteSupplyingSpliterator$OfRef.tryAdvance(StreamSpliterators.java:1361)
 at java.util.stream.StreamSpliterators$WrappingSpliterator.lambda$initPartialTraversalState$0(StreamSpliterators.java:295)
 at java.util.stream.StreamSpliterators$AbstractWrappingSpliterator.fillBuffer(StreamSpliterators.java:207)
 at java.util.stream.StreamSpliterators$AbstractWrappingSpliterator.doAdvance(StreamSpliterators.java:162)
...
```

You can reproduce it with:

```
mvn test -pl core -Dtest=ComponentizedGeneratorsIsolateConfigurationFromComponentsTest
```

Please find the cause of this failure in the code and fix it.


## repair-nio-quickcheck4862-L2-flaky

Mutated line (core/src/main/java/com/pholser/junit/quickcheck/internal/generator/GeneratorRepository.java:406): `;`

Forbidden-term hits: none

## `PropertyParameterConfigurationIsolationTest` fails in `core`

The test `acrossParametersOfSameParameterizedType` in `com.pholser.junit.quickcheck.PropertyParameterConfigurationIsolationTest` is failing:

```
Expected: has 0 failures
     but: was <
Time: 0.001
There was 1 failure:
1) holds(com.pholser.junit.quickcheck.PropertyParameterConfigurationIsolationTest$ParametersOfSameParameterizedType)
java.lang.IndexOutOfBoundsException: Index: 0, Size: 0
 at java.util.ArrayList.rangeCheck(ArrayList.java:659)
 at java.util.ArrayList.get(ArrayList.java:435)
 at java.util.Collections$UnmodifiableList.get(Collections.java:1311)
 at com.pholser.junit.quickcheck.test.generator.ABox.generate(ABox.java:45)
 at com.pholser.junit.quickcheck.test.generator.ABox.generate(ABox.java:33)
 at com.pholser.junit.quickcheck.internal.generator.PropertyParameterGenerationContext.generate(PropertyParameterGenerationContext.java:84)
 at com.pholser.junit.quickcheck.internal.SeededValue.<init>(SeededValue.java:37)
 at java.util.stream.ReferencePipeline$3$1.accept(ReferencePipeline.java:193)
 at java.util.ArrayList$ArrayListSpliterator.forEachRemaining(ArrayList.java:1384)
 at java.util.stream.AbstractPipeline.copyInto(AbstractPipeline.java:482)
 at java.util.stream.AbstractPipeline.wrapAndCopyInto(AbstractPipeline.java:472)
 at java.util.stream.ReduceOps$ReduceOp.evaluateSequential(ReduceOps.java:708)
 at java.util.stream.AbstractPipeline.evaluate(AbstractPipeline.java:234)
 at java.util.stream.ReferencePipeline.collect(ReferencePipeline.java:566)
 at com.pholser.junit.quickcheck.internal.sampling.TupleParameterSampler.lambda$sample$0(TupleParameterSampler.java:67)
 at java.util.stream.StreamSpliterators$InfiniteSupplyingSpliterator$OfRef.tryAdvance(StreamSpliterators.java:1361)
 at java.util.stream.StreamSpliterators$WrappingSpliterator.lambda$initPartialTraversalState$0(StreamSpliterators.java:295)
 at java.util.stream.StreamSpliterators$AbstractWrappingSpliterator.fillBuffer(StreamSpliterators.java:207)
 at java.util.stream.StreamSpliterators$AbstractWrappingSpliterator.doAdvance(StreamSpliterators.java:162)
...
```

You can reproduce it with:

```
mvn test -pl core -Dtest=PropertyParameterConfigurationIsolationTest
```

Please find the cause of this failure in the code and fix it.


## repair-nio-quickcheckc1c19-L1-flaky

Mutated line (core/src/main/java/com/pholser/junit/quickcheck/internal/ParameterTypeContext.java:165): `for (int i = 0; i < parameters.length; --i) {`

Forbidden-term hits: none

## `ComposedObjectsTest` fails in `core`

The test `askingForGeneratorsByConstructor` in `com.pholser.junit.quickcheck.ComposedObjectsTest` is failing:

```
Expected: has 0 failures
     but: was <
Time: 0.001
There was 1 failure:
1) holds(com.pholser.junit.quickcheck.ComposedObjectsTest$ByConstructor)
java.lang.ArrayIndexOutOfBoundsException: -1
 at com.pholser.junit.quickcheck.internal.ParameterTypeContext.parameterIndex(ParameterTypeContext.java:166)
 at com.pholser.junit.quickcheck.internal.ParameterTypeContext.forParameter(ParameterTypeContext.java:110)
 at com.pholser.junit.quickcheck.internal.generator.GeneratorRepository.parameter(GeneratorRepository.java:173)
 at com.pholser.junit.quickcheck.generator.Ctor.provide(Ctor.java:92)
 at com.pholser.junit.quickcheck.internal.generator.GeneratorRepository.constructor(GeneratorRepository.java:143)
 at com.pholser.junit.quickcheck.ComposedObjectsTest$ByConstructor$MakeA.generate(ComposedObjectsTest.java:191)
 at com.pholser.junit.quickcheck.ComposedObjectsTest$ByConstructor$MakeA.generate(ComposedObjectsTest.java:181)
 at com.pholser.junit.quickcheck.internal.generator.PropertyParameterGenerationContext.generate(PropertyParameterGenerationContext.java:84)
 at com.pholser.junit.quickcheck.internal.SeededValue.<init>(SeededValue.java:37)
 at java.util.stream.ReferencePipeline$3$1.accept(ReferencePipeline.java:193)
 at java.util.ArrayList$ArrayListSpliterator.forEachRemaining(ArrayList.java:1384)
 at java.util.stream.AbstractPipeline.copyInto(AbstractPipeline.java:482)
 at java.util.stream.AbstractPipeline.wrapAndCopyInto(AbstractPipeline.java:472)
 at java.util.stream.ReduceOps$ReduceOp.evaluateSequential(ReduceOps.java:708)
 at java.util.stream.AbstractPipeline.evaluate(AbstractPipeline.java:234)
 at java.util.stream.ReferencePipeline.collect(ReferencePipeline.java:566)
 at com.pholser.junit.quickcheck.internal.sampling.TupleParameterSampler.lambda$sample$0(TupleParameterSampler.java:67)
 at java.util.stream.StreamSpliterators$InfiniteSupplyingSpliterator$OfRef.tryAdvance(StreamSpliterators.java:1361)
 at java.util.stream.StreamSpliterators$WrappingSpliterator.lambda$in
```

You can reproduce it with:

```
mvn test -pl core -Dtest=ComposedObjectsTest
```

Please find the cause of this failure in the code and fix it.


## repair-nio-quickcheckc1c19-L2-flaky

Mutated line (core/src/main/java/com/pholser/junit/quickcheck/internal/ParameterTypeContext.java:165): `for (int i = 0; i < parameters.length; --i) {`

Forbidden-term hits: none

## `ExhaustingAGivenSetButIncludingAnotherTest` fails in `core`

The test `manyParameters` in `com.pholser.junit.quickcheck.ExhaustingAGivenSetButIncludingAnotherTest` is failing:

```
Expected: has 0 failures
     but: was <
Time: 0
There was 1 failure:
1) shouldHold(com.pholser.junit.quickcheck.ExhaustingAGivenSetButIncludingAnotherTest$ManyParameters)
java.lang.ArrayIndexOutOfBoundsException: -1
 at com.pholser.junit.quickcheck.internal.ParameterTypeContext.parameterIndex(ParameterTypeContext.java:166)
 at com.pholser.junit.quickcheck.internal.ParameterTypeContext.forParameter(ParameterTypeContext.java:151)
 at com.pholser.junit.quickcheck.runner.PropertyStatement.parameterContextFor(PropertyStatement.java:185)
 at com.pholser.junit.quickcheck.runner.PropertyStatement.lambda$evaluate$0(PropertyStatement.java:93)
 at java.util.stream.ReferencePipeline$3$1.accept(ReferencePipeline.java:193)
 at java.util.Spliterators$ArraySpliterator.forEachRemaining(Spliterators.java:948)
 at java.util.stream.AbstractPipeline.copyInto(AbstractPipeline.java:482)
 at java.util.stream.AbstractPipeline.wrapAndCopyInto(AbstractPipeline.java:472)
 at java.util.stream.ReduceOps$ReduceOp.evaluateSequential(ReduceOps.java:708)
 at java.util.stream.AbstractPipeline.evaluate(AbstractPipeline.java:234)
 at java.util.stream.ReferencePipeline.collect(ReferencePipeline.java:566)
 at com.pholser.junit.quickcheck.runner.PropertyStatement.evaluate(PropertyStatement.java:101)
 at org.junit.runners.BlockJUnit4ClassRunner$1.evaluate(BlockJUnit4ClassRunner.java:100)
 at org.junit.runners.ParentRunner.runLeaf(ParentRunner.java:366)
 at org.junit.runners.BlockJUnit4ClassRunner.runChild(BlockJUnit4ClassRunner.java:103)
 at org.junit.runners.BlockJUnit4ClassRunner.runChild(BlockJUnit4ClassRunner.java:63)
 at org.junit.runners.ParentRunner$4.run(ParentRunner.java:331)
 at org.junit.runners.ParentRunner$1.schedule(ParentRunner.java:79)
 at org.junit.runners.ParentRunner.runChildren(ParentRunner.java:329)
...
```

You can reproduce it with:

```
mvn test -pl core -Dtest=ExhaustingAGivenSetButIncludingAnotherTest
```

Please find the cause of this failure in the code and fix it.


## repair-od-ormlitecore59309e83-L1-flaky

Mutated line (src/main/java/com/j256/ormlite/field/FieldType.java:613): `;`

Forbidden-term hits: none

## `BaseDaoImplTest` fails in `ormlitecore59309e5`

The test `testForeignAutoRefresh` in `com.j256.ormlite.dao.BaseDaoImplTest` is failing:

```
expected: not <null>
```

You can reproduce it with:

```
mvn test -Dtest=BaseDaoImplTest
```

Please find the cause of this failure in the code and fix it.


## repair-od-ormlitecore59309e83-L2-flaky

Mutated line (src/main/java/com/j256/ormlite/field/FieldType.java:613): `;`

Forbidden-term hits: none

## `DatabaseConnectionProxyFactoryTest` fails in `ormlitecore59309e5`

The test `testChangeInsertValue` in `com.j256.ormlite.support.DatabaseConnectionProxyFactoryTest` is failing:

```
expected: not <null>
```

You can reproduce it with:

```
mvn test -Dtest=DatabaseConnectionProxyFactoryTest
```

Please find the cause of this failure in the code and fix it.


## repair-od-shardingsphereelasticjobelasticjoblitecore90e3a7f-L1-flaky

Mutated line (elastic-job-lite-core/src/main/java/io/elasticjob/lite/reg/zookeeper/ZookeeperRegistryCenter.java:232): `;`

Forbidden-term hits: none

## `ZookeeperRegistryCenterQueryWithoutCacheTest` fails in `elastic-job-lite-core`

The test `assertGetRegistryCenterTime` in `io.elasticjob.lite.reg.zookeeper.ZookeeperRegistryCenterQueryWithoutCacheTest` is failing:

```
(no message)
```

You can reproduce it with:

```
mvn test -pl elastic-job-lite-core -Dtest=ZookeeperRegistryCenterQueryWithoutCacheTest
```

Please find the cause of this failure in the code and fix it.


## repair-od-shardingsphereelasticjobelasticjoblitecore90e3a7f-L2-flaky

Mutated line (elastic-job-lite-core/src/main/java/io/elasticjob/lite/reg/zookeeper/ZookeeperRegistryCenter.java:232): `;`

Forbidden-term hits: none

## `ZookeeperRegistryCenterModifyTest` fails in `elastic-job-lite-core`

The test `assertUpdate` in `io.elasticjob.lite.reg.zookeeper.ZookeeperRegistryCenterModifyTest` is failing:

```
Expected: is "after_update"
     but: was "before_update"
```

You can reproduce it with:

```
mvn test -pl elastic-job-lite-core -Dtest=ZookeeperRegistryCenterModifyTest
```

Please find the cause of this failure in the code and fix it.


## repair-od-wildflynaming3a83b7b9-L1-flaky

Mutated line (naming/src/main/java/org/jboss/as/naming/ServiceBasedNamingStore.java:86): `if (lower == null && lower.isParentOf(lookupName)) {`

Forbidden-term hits: none

## `WritableServiceBasedNamingStoreTestCase` fails in `naming`

The test `testMultipleOwnersBindingReferences` in `org.jboss.as.naming.WritableServiceBasedNamingStoreTestCase` is failing:

```
(no message)
```

You can reproduce it with:

```
mvn test -pl naming -Dtest=WritableServiceBasedNamingStoreTestCase
```

Please find the cause of this failure in the code and fix it.


## repair-od-wildflynaming3a83b7b9-L2-flaky

Mutated line (naming/src/main/java/org/jboss/as/naming/ServiceBasedNamingStore.java:86): `if (lower == null && lower.isParentOf(lookupName)) {`

Forbidden-term hits: none

## `ServiceBasedNamingStoreTestCase` fails in `naming`

The test `testStoredContext` in `org.jboss.as.naming.ServiceBasedNamingStoreTestCase` is failing:

```
foo-stored/again/blah/blah2 -- service jboss.foo-stored.again.blah.blah2
```

You can reproduce it with:

```
mvn test -pl naming -Dtest=ServiceBasedNamingStoreTestCase
```

Please find the cause of this failure in the code and fix it.


## repair-td-HADOOP-10394_testDoFilterAuthenticationWithInvalidToken-L2-flaky

Mutated line (hadoop-common-project/hadoop-auth/src/main/java/org/apache/hadoop/security/authentication/server/AuthenticationFilter.java:402): `;`

Forbidden-term hits: none

## `TestAuthenticationFilter` fails in `hadoop-common-project/hadoop-auth`

The test `testDoFilterAuthenticatedExpired` in `org.apache.hadoop.security.authentication.server.TestAuthenticationFilter` is failing:

```
Wanted but not invoked:
httpServletResponse.sendError(401, <any>);
-> at org.apache.hadoop.security.authentication.server.TestAuthenticationFilter.verifyUnauthorized(TestAuthenticationFilter.java:636)

However, there were other interactions with this mock:
-> at org.apache.hadoop.security.authentication.server.TestAuthenticationFilter$DummyAuthenticationHandler.authenticate(TestAuthenticationFilter.java:128)
-> at org.apache.hadoop.security.authentication.server.AuthenticationFilter.doFilter(AuthenticationFilter.java:399)
-> at org.apache.hadoop.security.authentication.server.AuthenticationFilter.createAuthCookie(AuthenticationFilter.java:446)
```

You can reproduce it with:

```
mvn test -pl hadoop-common-project/hadoop-auth -Dtest=TestAuthenticationFilter
```

Please find the cause of this failure in the code and fix it.

