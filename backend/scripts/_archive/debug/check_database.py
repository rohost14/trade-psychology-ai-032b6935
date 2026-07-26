"""
Database Schema Inspector
Checks all tables and columns in Supabase PostgreSQL
"""

import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = "postgresql+asyncpg://postgres:Rao141820nav@db.gllhexxongqgfgkvrfjk.supabase.co:5432/postgres"

async def inspect_database():
    engine = create_async_engine(DATABASE_URL)

    async with engine.connect() as conn:
        # Get all tables in public schema
        tables_query = text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
            AND table_type = 'BASE TABLE'
            ORDER BY table_name;
        """)

        result = await conn.execute(tables_query)
        tables = [row[0] for row in result.fetchall()]

        print("=" * 80)
        print(f"SUPABASE DATABASE SCHEMA - Found {len(tables)} tables")
        print("=" * 80)

        for table in tables:
            print(f"\n[TABLE] {table}")
            print("-" * 60)

            # Get columns for this table
            columns_query = text(f"""
                SELECT
                    column_name,
                    data_type,
                    is_nullable,
                    column_default
                FROM information_schema.columns
                WHERE table_schema = 'public'
                AND table_name = :table_name
                ORDER BY ordinal_position;
            """)

            cols_result = await conn.execute(columns_query, {"table_name": table})
            columns = cols_result.fetchall()

            for col in columns:
                nullable = "NULL" if col[2] == "YES" else "NOT NULL"
                default = f" DEFAULT {col[3][:30]}..." if col[3] and len(str(col[3])) > 30 else (f" DEFAULT {col[3]}" if col[3] else "")
                print(f"  • {col[0]:<30} {col[1]:<20} {nullable:<10}{default}")

        # Get foreign key relationships
        print("\n" + "=" * 80)
        print("FOREIGN KEY RELATIONSHIPS")
        print("=" * 80)

        fk_query = text("""
            SELECT
                tc.table_name AS from_table,
                kcu.column_name AS from_column,
                ccu.table_name AS to_table,
                ccu.column_name AS to_column
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
            AND tc.table_schema = 'public'
            ORDER BY tc.table_name;
        """)

        fk_result = await conn.execute(fk_query)
        fks = fk_result.fetchall()

        for fk in fks:
            print(f"  {fk[0]}.{fk[1]} → {fk[2]}.{fk[3]}")

        # Get indexes
        print("\n" + "=" * 80)
        print("INDEXES")
        print("=" * 80)

        idx_query = text("""
            SELECT
                tablename,
                indexname,
                indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
            ORDER BY tablename, indexname;
        """)

        idx_result = await conn.execute(idx_query)
        indexes = idx_result.fetchall()

        current_table = ""
        for idx in indexes:
            if idx[0] != current_table:
                current_table = idx[0]
                print(f"\n  [TABLE] {current_table}:")
            print(f"    • {idx[1]}")

        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"Total Tables: {len(tables)}")
        print(f"Total Foreign Keys: {len(fks)}")
        print(f"Total Indexes: {len(indexes)}")
        print("Tables:", ", ".join(tables))

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(inspect_database())
