# Unit Testing Cheat Sheet

## Testing Libraries and Frameworks

- Jest: Primary testing framework

## Mocking and Stubbing Strategies

1. Jest Mock Functions
   - Use `jest.fn()` to create mock functions
   - Example:
     ```javascript
     const mockCallback = jest.fn();
     ```

2. Manual Mocks
   - Create mock files in `__mocks__` directory
   - Example:
     ```javascript
     // __mocks__/externalModule.js
     module.exports = {
       someFunction: jest.fn()
     };
     ```

3. Mocking Modules
   - Use `jest.mock()` to mock entire modules
   - Example:
     ```javascript
     jest.mock('axios');
     ```

## Fake Implementations

1. In-memory Databases
   - Use arrays or objects to simulate database operations
   - Example:
     ```javascript
     const fakeDb = [];
     const addItem = (item) => fakeDb.push(item);
     const getItems = () => fakeDb;
     ```

2. Fake Timers
   - Use `jest.useFakeTimers()` for time-based tests
   - Example:
     ```javascript
     jest.useFakeTimers();
     jest.advanceTimersByTime(1000);
     ```

## Test Structure

1. Describe Blocks
   - Group related tests
   - Example:
     ```javascript
     describe('UserService', () => {
       // tests go here
     });
     ```

2. Lifecycle Hooks
   - Use `beforeEach()` and `afterEach()` for setup and teardown
   - Example:
     ```javascript
     beforeEach(() => {
       // setup code
     });
     ```

3. Async Testing
   - Use `async/await` or `done` callback for asynchronous tests
   - Example:
     ```javascript
     test('async operation', async () => {
       await expect(asyncFunction()).resolves.toBe('result');
     });
     ```

## Assertions

1. Jest Matchers
   - Use built-in matchers like `toBe()`, `toEqual()`, `toHaveBeenCalled()`
   - Example:
     ```javascript
     expect(result).toBe(5);
     expect(mockFunction).toHaveBeenCalledTimes(1);
     ```

2. Custom Matchers
   - Extend Jest with custom matchers for specific assertions
   - Example:
     ```javascript
     expect.extend({
       toBeWithinRange(received, floor, ceiling) {
         // custom matcher logic
       }
     });
     ```

## Error Handling

1. Expecting Errors
   - Use `toThrow()` matcher for error assertions
   - Example:
     ```javascript
     expect(() => {
       throwingFunction();
     }).toThrow('Error message');
     ```

## Code Coverage

- Use Jest's built-in coverage reporting
- Example command: `jest --coverage`

## Best Practices

1. Test Isolation
   - Each test should be independent and not rely on other tests
2. Descriptive Test Names
   - Use clear and descriptive names for test cases
3. Arrange-Act-Assert (AAA) Pattern
   - Structure tests with clear setup, execution, and assertion phases
4. Test Edge Cases
   - Include tests for boundary conditions and error scenarios