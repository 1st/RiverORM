from riverorm import constants
from riverorm.db import BaseDatabase, get_database


def test_db_connection():
    """Test that get_database returns the correct database instance and caching works."""
    conn1 = get_database(constants.POSTGRES, debug=True)
    conn2 = get_database(constants.POSTGRES, debug=True)
    conn3 = get_database(constants.POSTGRES, debug=False)
    conn4 = get_database(constants.MYSQL, debug=True)
    conn5 = get_database(constants.MYSQL, debug=True)
    conn6 = get_database(constants.MYSQL, debug=False)

    assert isinstance(conn1, BaseDatabase)
    assert isinstance(conn4, BaseDatabase)
    assert conn1 is conn2  # Cached instance
    assert conn4 is conn5  # Cached instance
    assert conn1 is not conn3  # Different debug setting
    assert conn4 is not conn6  # Different debug setting
    assert conn1 is not conn4  # Different DB types
    assert conn3 is not conn6  # Different DB types


def test_unsupported_db():
    """Test that requesting an unsupported database raises ValueError."""
    try:
        get_database("unsupported_db")
    except ValueError as e:
        assert str(e) == "Unsupported database type: unsupported_db"
    else:
        assert False, "Expected ValueError for unsupported DB type"
