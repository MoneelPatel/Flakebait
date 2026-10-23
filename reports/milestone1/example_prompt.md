## Example prompts

**L1** (`repair-id-commonslang1163e17testReflectionHashCodeExcludeFields-L1-flaky`):

````markdown
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
````

**L2** (`repair-id-commonslang1163e17testReflectionHashCodeExcludeFields-L2-flaky`):

````markdown
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
````
