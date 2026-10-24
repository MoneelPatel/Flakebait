## Example prompts

**L1** (`repair-nio-quickcheckc1c19-L1-flaky`):

````markdown
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
````

**L2** (`repair-nio-quickcheckc1c19-L2-flaky`):

````markdown
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
````
