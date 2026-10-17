You need to configure an operation type so its operations show up in the weighing assistant.

To do so:

1. Go to *Configuration > Operations Types* and choose the one you want to configure.
2. Set *Weighing operations* on.
3. You can choose your desired *Weighing label report*.
4. If you want to print your labels automatically, set *Print weighing label* on.

If you don't have any product with a unit of weight, you'll have to add some.

- Allow to show the units of measure in your config settings if isn't ready yet.
- Add some products with a unit of weight (kilograms, grams, etc.).
- Place some pending operations for those products.

If you want to use the weighing system for other operations you can set the configuration parameter
`stock_weighing.any_operation_actions` to a true value. You'll be able to record other
values.
