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


## repair-id-typescriptgeneratortypescriptgeneratorcore0841f94testSingleEnum-L1-flaky

Mutated line (typescript-generator-core/src/main/java/cz/habarta/typescript/generator/Settings.java:362): `if (features.npmDevDependencies == null) {`

Forbidden-term hits: none

## `EnumConstantsExtensionTest` fails in `typescript-generator-core`

The test `testSorting` in `cz.habarta.typescript.generator.EnumConstantsExtensionTest` is failing:

```
(no message)
```

You can reproduce it with:

```
mvn test -pl typescript-generator-core -Dtest=EnumConstantsExtensionTest
```

Please find the cause of this failure in the code and fix it.


## repair-id-typescriptgeneratortypescriptgeneratorcore0841f94testSingleEnum-L2-flaky

Mutated line (typescript-generator-core/src/main/java/cz/habarta/typescript/generator/Settings.java:362): `if (features.npmDevDependencies == null) {`

Forbidden-term hits: none

## `EnumTest` fails in `typescript-generator-core`

The test `testEnumsAsPascalCaseWithClassEnumPattern` in `cz.habarta.typescript.generator.EnumTest` is failing:

```
(no message)
```

You can reproduce it with:

```
mvn test -pl typescript-generator-core -Dtest=EnumTest
```

Please find the cause of this failure in the code and fix it.


## repair-nio-quickcheck4852-L1-flaky

Mutated line (core/src/main/java/com/pholser/junit/quickcheck/internal/generator/GeneratorRepository.java:249): `return null;`

Forbidden-term hits: none

## `PropertiesWithExplicitGeneratorsTest` fails in `core`

The test `explicitPrimitiveByte` in `com.pholser.junit.quickcheck.PropertiesWithExplicitGeneratorsTest` is failing:

```
Expected: has 0 failures
     but: was <
Time: 0
There was 1 failure:
1) shouldHold(com.pholser.junit.quickcheck.PropertiesWithExplicitGeneratorsTest$ExplicitPrimitiveByte)
java.lang.NullPointerException
 at com.pholser.junit.quickcheck.internal.generator.GeneratorRepository.produceGenerator(GeneratorRepository.java:239)
 at com.pholser.junit.quickcheck.internal.sampling.TupleParameterSampler.decideGenerator(TupleParameterSampler.java:97)
 at com.pholser.junit.quickcheck.internal.generator.PropertyParameterGenerationContext.<init>(PropertyParameterGenerationContext.java:67)
 at com.pholser.junit.quickcheck.runner.PropertyStatement.lambda$evaluate$1(PropertyStatement.java:94)
 at java.util.stream.ReferencePipeline$3$1.accept(ReferencePipeline.java:193)
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
...
```

You can reproduce it with:

```
mvn test -pl core -Dtest=PropertiesWithExplicitGeneratorsTest
```

Please find the cause of this failure in the code and fix it.


## repair-nio-quickcheck4852-L2-flaky

Mutated line (core/src/main/java/com/pholser/junit/quickcheck/internal/generator/GeneratorRepository.java:249): `return null;`

Forbidden-term hits: none

## `ExhaustingAGivenSetButIncludingAnotherTest` fails in `core`

The test `primitiveBooleans` in `com.pholser.junit.quickcheck.ExhaustingAGivenSetButIncludingAnotherTest` is failing:

```
Expected: has 0 failures
     but: was <
Time: 0
There was 1 failure:
1) shouldHold(com.pholser.junit.quickcheck.ExhaustingAGivenSetButIncludingAnotherTest$PrimitiveBooleans)
java.lang.NullPointerException
 at com.pholser.junit.quickcheck.internal.generator.GeneratorRepository.produceGenerator(GeneratorRepository.java:239)
 at com.pholser.junit.quickcheck.internal.sampling.ExhaustiveParameterSampler.decideGenerator(ExhaustiveParameterSampler.java:125)
 at com.pholser.junit.quickcheck.internal.generator.PropertyParameterGenerationContext.<init>(PropertyParameterGenerationContext.java:67)
 at com.pholser.junit.quickcheck.runner.PropertyStatement.lambda$evaluate$1(PropertyStatement.java:94)
 at java.util.stream.ReferencePipeline$3$1.accept(ReferencePipeline.java:193)
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
...
```

You can reproduce it with:

```
mvn test -pl core -Dtest=ExhaustingAGivenSetButIncludingAnotherTest
```

Please find the cause of this failure in the code and fix it.


## repair-nio-quickcheckc1c19-L1-flaky

Mutated line (core/src/main/java/com/pholser/junit/quickcheck/internal/ParameterTypeContext.java:165): `for (int i = 0; i < parameters.length; --i) {`

Forbidden-term hits: none

## `PropertyTupleSampleSizeTest` fails in `core`

The test `trialCountHoldsForEntirePropertyRatherThanIndividualParameters` in `com.pholser.junit.quickcheck.PropertyTupleSampleSizeTest` is failing:

```
Expected: has 0 failures
     but: was <
Time: 0
There was 1 failure:
1) shouldHold(com.pholser.junit.quickcheck.PropertyTupleSampleSizeTest$ForValuesOfMultipleParameters)
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
mvn test -pl core -Dtest=PropertyTupleSampleSizeTest
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

Mutated line (src/main/java/com/j256/ormlite/field/FieldType.java:550): `(val != null ? "null" : val.getClass()), val);`

Forbidden-term hits: none

## `BigDecimalTypeTest` fails in `ormlitecore59309e5`

The test `testBigDecimalNull` in `com.j256.ormlite.field.types.BigDecimalTypeTest` is failing:

```
(no message)
```

You can reproduce it with:

```
mvn test -Dtest=BigDecimalTypeTest
```

Please find the cause of this failure in the code and fix it.


## repair-od-ormlitecore59309e83-L2-flaky

Mutated line (src/main/java/com/j256/ormlite/field/FieldType.java:550): `(val != null ? "null" : val.getClass()), val);`

Forbidden-term hits: none

## `DatabaseConnectionProxyFactoryTest` fails in `ormlitecore59309e5`

The test `testChangeInsertValue` in `com.j256.ormlite.support.DatabaseConnectionProxyFactoryTest` is failing:

```
(no message)
```

You can reproduce it with:

```
mvn test -Dtest=DatabaseConnectionProxyFactoryTest
```

Please find the cause of this failure in the code and fix it.


## repair-td-HADOOP-10394_testDoFilterAuthenticationWithInvalidToken-L1-flaky

Mutated line (hadoop-common-project/hadoop-auth/src/main/java/org/apache/hadoop/security/authentication/server/AuthenticationFilter.java:402): `;`

Forbidden-term hits: none

## `TestPseudoAuthenticator` fails in `hadoop-common-project/hadoop-auth`

The test `testAnonymousDisallowed` in `org.apache.hadoop.security.authentication.client.TestPseudoAuthenticator` is failing:

```
expected:<401> but was:<200>
```

You can reproduce it with:

```
mvn test -pl hadoop-common-project/hadoop-auth -Dtest=TestPseudoAuthenticator
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

